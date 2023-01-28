/**
 * SPA for openelec
 * Compiled with webpack
 */

import $ from 'jquery';

import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import geojsonExtent from '@mapbox/geojson-extent';
import osmtogeojson from 'osmtogeojson';

import 'bootstrap/js/dist/modal';
import 'bootstrap/dist/css/bootstrap.min.css';

import 'bootstrap-slider';
import 'bootstrap-slider/dist/css/bootstrap-slider.min.css';

import 'typeface-chivo';
import JSZip from 'jszip';

import './style.css';
import { sliderConfigs, summaryConfigs, countries, layerColors } from './config.js';
// eslint-disable-next-line no-undef
const vars = require('./vars.js');

import * as d3 from 'd3';

// eslint-disable-next-line no-undef
const flags = importImages(require.context('./flags', false, /\.(png|jpe?g|svg)$/));

// Use local API URL for dev, and server for prod
let API = vars.API;
let dataloc = '/data/';

// object for Mapbox GL map
let map;

// all layers are placed under this layer
let firstSymbolId = 'place-village';

// name of satellite layer to hide
let satelliteLayer = 'mapbox-satellite';

// can be one of ['plan', 'find'] 
let activeModel;

// boolean
let zoomed;

// for dyamic (time step) modelling
let currentStep = 1;
let dynamic = true;
let dynamicSummary;
const disabledDynamic = ['ethiopia', 'kenya', 'tanzania'];

// keep track of the country we're looking at
let country;

// current values of input parametres
const sliderParams = {};

// objects for right sidebar legend and summary results
const summaryHtml = {'plan-nat': '', 'plan-loc': '', 'find-nat': ''};
const legendHtml = {'plan-nat': '', 'plan-loc': '', 'find-nat': ''};

// message displayed at national-level display
const clickMsg = '<p>Click on a cluster to optimise local network</p>';
const clickBtn = '<button type="button" class="btn btn-warning btn-block" id="btn-zoom-out">Click to zoom out</button>';

// keep track of local bounding box
let clusterBounds;
let countryBounds;
let layersAdded = false;

// for backward compatibility, maintain both options
let passFullVillageGeojson = false;

// to intialise buildings layer before we have the GeoJSON
const emptyGeoJSON = { 'type': 'FeatureCollection', 'features': [] };

// standard styling for clusters
const clusterStylingPlan = [
  'match',
  ['get', 'type'],
  'densify', layerColors.clustersPlan.densify,
  'grid', layerColors.clustersPlan.grid,
  'offgrid', layerColors.clustersPlan.offgrid,
  'none', layerColors.clustersPlan.none,
  layerColors.clustersPlan.default
];

// find styling for clusters
const clusterStylingFind = {
  property: 'score',
  stops: [
    [0, layerColors.clustersFind.bottom],
    [1, layerColors.clustersFind.top]
  ],
  default: layerColors.clustersPlan.default
};

// Call the Lambda API to get it loaded
//$.ajax({
  //url: API + 'warm_engines',
  //data: '',
  //success: function(data) {
    //console.log(data.message);
  //}
//});

// Call init() function on DOM load
$(document).ready(init);

/**
 * Called on DOM load.
 * Create map and assign button click calls.
 */
function init() {
  // go straight to video modal if it's in the URL
  if (window.location.href.indexOf('#modalVideo') != -1) {
    $('#modalVideo').modal('show');
  }
  createMap();

  $('#go-home').click(home);
  $('#go-about').click(about);
  //$('#run-model').click(runModel);
  $('#download-results').click(downloadResults);
  $('#go-plan').click(plan);
  $('#go-plan-big').click(plan);
  $('#go-find').click(find);
  $('#go-find-big').click(find);
  $('#change-country').click(chooseCountry);
  $('#prev-step').click(prevStep);
  $('#next-step').click(nextStep);

  let countryList = $('#country-list');
  for (let countryName in countries) {
    let countryCap = capFirst(countryName);
    countryList.append('<a href="#" class="choose-country" id="' + countryName + '"><div class="card shadow my-3" style="width: 10rem;"><img class="card-img-top" src="' + flags['flag-' + countryName + '.png'] + '" alt="flag"><div class="card-body"><h5 class="card-title">' + countryCap + '</h5></div></div></a><br>');
  }

  $('.choose-country').click(explore);

  $('.js-loading-bar').modal({
    backdrop: 'static',
    show: false
  });

  $('body').on('hidden.bs.modal', '.modal', function () {
    $('video').trigger('pause');
  });

  skipToCountry();
}

/**
 * Go straight to country if provided in URL args with ?country=<name>
 */
function skipToCountry() {
  let url = new URL(window.location.href);
  country = url.searchParams.get('country');
  if (country !== null) {
    setTimeout(function() {
      chooseCountry();
      find();
      explore();
    }, 1000);
  }
}


/**
 * Create the Mapbox GL map.
 */
function createMap() {
  mapboxgl.accessToken = 'pk.eyJ1IjoiY2FyZGVybmUiLCJhIjoiY2puMXN5cnBtNG53NDN2bnhlZ3h4b3RqcCJ9.eNjrtezXwvM7Ho1VSxo06w';
  map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/carderne/cjpnxmz1e0o7s2suj6vs2thza'
  });

  map.addControl(new mapboxgl.ScaleControl({
    maxWidth: 200,
    unit: 'metric',
  }), 'bottom-right');
  map.addControl(new mapboxgl.NavigationControl(), 'bottom-right');
}

/**
 * Add national layers (grid and clusters) for the country.
 */
function addMapLayers() {
  map.setLayoutProperty(satelliteLayer, 'visibility', 'none');
  createLayerSwitcher();

  map.addSource('clusters', { type: 'geojson', data: emptyGeoJSON });
  map.addLayer({
    'id': 'clusters',
    'type': 'fill',
    'source': 'clusters',
    'paint': {
      'fill-color': clusterStylingPlan,
      'fill-opacity': 0.5,
    }
  }, firstSymbolId);
  map.addLayer({
    'id': 'clusters-outline',
    'type': 'line',
    'source': 'clusters',
    'paint': {
      'line-color': clusterStylingPlan,
      'line-width': 2,
    }
  }, firstSymbolId);

  map.addSource('grid', { type: 'geojson', data: emptyGeoJSON });
  map.addLayer({
    'id': 'grid',
    'type': 'line',
    'source': 'grid',
    'layout': {
      'line-join': 'round',
      'line-cap': 'round'
    },
    'paint': {
      'line-color': layerColors.grid,
      'line-width': 2
    }
  }, firstSymbolId);

  map.addSource('buildings', { type: 'geojson', data: emptyGeoJSON });
  map.addLayer({
    'id': 'buildings',
    'type': 'fill',
    'source': 'buildings',
    'paint': {
      'fill-color': layerColors.buildings.default,
      'fill-opacity': 0.8
    }
  }, firstSymbolId);

  // Change the cursor to a pointer when the mouse is over the states layer.
  // And show hover popup
  map.on('mouseenter', 'clusters', mouseOverClusters);

  // Change it back to a pointer when it leaves.
  // And remove popup
  map.on('mouseleave', 'clusters', function () {
    map.getCanvas().style.cursor = '';
    popup.remove();
  });

  map.on('click', 'clusters', clusterClick);
}

// Create a popup, but don't add it to the map yet.
let popup = new mapboxgl.Popup({
  closeButton: false,
  closeOnClick: false
});

/**
 * 
 * @param {*} e 
 */
function mouseOverClusters(e) {
  map.getCanvas().style.cursor = 'pointer';

  let props = e.features[0].properties;
  let id = props.fid;
  let pop = props.pop.toFixed(0);
  let area = (props.area/1e6).toFixed(2);
  let ntl = props.ntl.toFixed(2);
  let gdp = props.gdp.toFixed(2);
  let grid = props.grid.toFixed(2);
  let travel = props.travel.toFixed(0);

  let text = '<strong>Cluster details</strong>' + '<p>ID: ' + id + '<br>Pop: ' + pop + 
             '<br>Size: ' + area + ' km2<br>NTL: ' + ntl + '<br>GDP: ' + gdp + 
             ' USD/p<br>Grid dist: ' + grid + ' km<br>Travel time: ' + travel + 
             ' hrs</p>';

  if (props.demand !== undefined && props.coverage !== undefined) {
    text += '<p>Demand: ' + props.demand.toFixed(0) + ' kWh/p/month' +
            '<br>Init coverage: ' + (100 * props.coverage).toFixed(0) + ' %</p>';
  }

  popup.setLngLat([e.lngLat.lng, e.lngLat.lat])
    .setHTML(text)
    .addTo(map);
}

/**
 * Called by the id=run-model button.
 * Calls a function depending on which model is currently active.
 */
function runModel() {
  $('#loading-bar').modal('show');

  if (zoomed) {
    runPlanLoc();
  } else if (activeModel == 'plan') {
    runPlanNat();
  } else if (activeModel == 'find') {
    runFindNat();
  }
}


/**
 * Run API call for planNat.
 */
function runPlanNat() {
  dynamic = $('#switch-dynamic').prop('checked');
  if (disabledDynamic.includes(country)) dynamic = false;

  sliderParams['plan-nat']['country'] = country;
  sliderParams['plan-nat']['access-urban'] = countries[country]['access-urban'];
  sliderParams['plan-nat']['access-rate'] = countries[country]['access-rate'];
  sliderParams['plan-nat']['dynamic'] = dynamic;
  sliderParams['plan-nat']['mtf'] = $('#switch-mtf').prop('checked');

  $.ajax({
    url: API + 'plan_nat',
    data: sliderParams['plan-nat'],
    success: showPlanNat,
    error: function () {
      $('#loading-bar').modal('hide');
    }
  });
}

/**
 * Run API call for planLoc.
 */
function runPlanLoc() {
  let west = clusterBounds[0];
  let south = clusterBounds[1];
  let east = clusterBounds[2];
  let north = clusterBounds[3];
  let bounds = south + ', ' + west + ', ' + north + ', ' + east;
  sliderParams['plan-loc']['bounds'] = bounds;

  if (sliderParams['plan-loc']['bounds']) {
    $.ajax({
      url: API + 'plan_loc',
      data: sliderParams['plan-loc'],
      contentType: 'application/json',
      success: showPlanLoc,
      error: function (e) {
        $('#loading-bar').modal('hide');
      }
    });
  } else {
    $('#map-announce').html('No building data found');
    setTimeout(resetAnnounce, 2000);
    $('#loading-bar').modal('hide');
  }
}

/**
 * Run API call for findNat.
 */
function runFindNat() {
  sliderParams['find-nat']['country'] = country;
  $.ajax({
    url: API + 'find_nat',
    data: sliderParams['find-nat'],
    success: showFindNat,
    error: function () {
      $('#loading-bar').modal('hide');
    }
  });
}


/**
 * 
 */
function prevStep() {
  if (currentStep > 1) {
    currentStep -= 1;
    let currentYear = parseInt($('#step-year').html());
    $('#step-year').html(currentYear -= 5);
    dynamicPlanNat(currentStep);
  }
}


/**
 * 
 */
function nextStep() {
  if (currentStep < 4) {
    currentStep += 1;
    let currentYear = parseInt($('#step-year').html());
    $('#step-year').html(currentYear += 5);
    dynamicPlanNat(currentStep);
  }
}


/**
 * 
 * @param {*} step 
 */
function dynamicPlanNat(step) {
  let hiddenNetwork = [
    'all',
    ['<=', 'stage', step]
  ];
  map.setFilter('network', hiddenNetwork);

  let type = 'type_' + step;
  let clusterStylingDynamic = [
    'match',
    ['get', type],
    'densify', layerColors.clustersPlan.densify,
    'grid', layerColors.clustersPlan.grid,
    'offgrid', layerColors.clustersPlan.offgrid,
    'none', layerColors.clustersPlan.none,
    layerColors.clustersPlan.default
  ];
  map.setPaintProperty('clusters', 'fill-color', clusterStylingDynamic);
  map.setPaintProperty('clusters-outline', 'line-color', clusterStylingDynamic);

  updateSummary('plan-nat', dynamicSummary[step]);
  map.resize();
}


/**
 * Update map and summary pane with results from model.
 * 
 * @param {*} data 
 */
function showPlanNat(data) {

  if (dynamic) {
    dynamicSummary = data.summary;
    data.summary = data.summary[1];
    show('dynamic-box');
    currentStep = 1;
    $('#step-year').html(2025);
  } else {
    hide('dynamic-box');
  }

  if (map.getSource('network')) {
    map.getSource('network').setData(data.network);
  } else {
    map.addSource('network', { type: 'geojson', data: data.network });
    map.addLayer({
      'id': 'network',
      'type': 'line',
      'source': 'network',
      'layout': {
        'line-join': 'round',
        'line-cap': 'round'
      },
      'paint': {
        'line-color': layerColors.network,
        'line-width': 3
      }
    }, firstSymbolId);
  }

  let hiddenNetwork = [
    'all',
    ['==', 'stage', 1]
  ];
  map.setFilter('network', hiddenNetwork);
  if (!dynamic) map.setFilter('network');

  map.getSource('clusters').setData(data.clusters);
  map.setPaintProperty('clusters', 'fill-color', clusterStylingPlan);
  map.setPaintProperty('clusters-outline', 'line-color', clusterStylingPlan);

  updateSummary('plan-nat', data.summary);
  map.resize();

  $('#loading-bar').modal('hide');
}


/**
 * After model run, display summary results and
 * update map with network and connected buildings.
 * 
 * @param {*} data 
 */
function showPlanLoc(data) {
  map.getSource('buildings').setData(data.buildings);
  map.setPaintProperty('buildings', 'fill-color', {
    property: 'conn',
    stops: [[0, layerColors.buildings.shs], [1, layerColors.buildings.mg]]
  });

  if (map.getSource('lv')) {
    map.getSource('lv').setData(data.network);
  } else {
    map.addSource('lv', { type: 'geojson', data: data.network });
    map.addLayer({
      'id': 'lv',
      'type': 'line',
      'source': 'lv',
      'layout': {
        'line-join': 'round',
        'line-cap': 'round'
      },
      'paint': {
        'line-color': layerColors.lv,
        'line-width': 3
      }
    }, firstSymbolId);
  }

  updateSummary('plan-loc', data.summary); 
  map.resize();
  $('#loading-bar').modal('hide');
}

/**
 * Update map and summary pane with model results.
 * 
 * @param {*} data 
 */
function showFindNat(data) {
  map.getSource('clusters').setData(data.clusters);
  map.setPaintProperty('clusters', 'fill-color', clusterStylingFind);
  map.setPaintProperty('clusters-outline', 'line-color', clusterStylingFind);

  updateSummary('find-nat', data.summary);
  map.resize();
  $('#loading-bar').modal('hide');
}

/**
 * Get the bounding box from the clicked cluster,
 * and call prepLanLoc().
 * 
 * @param {*} e 
 */
function clusterClick(e) {
  let features = map.queryRenderedFeatures(e.point);
  clusterBounds = geojsonExtent(features[0].geometry);
  prepPlanLoc();
}

/**
 * Zoom to clicked cluster and prepare for planLoc.
 */
function prepPlanLoc() {
  map.fitBounds(clusterBounds, {padding: 20});
  map.setPaintProperty('clusters', 'fill-opacity', 0.1);
  hide('dynamic-box');

  $('#map-announce').html(clickBtn);
  $('#btn-zoom-out').click(zoomToNat);
  $('#download-results').html('Download results');
  map.on('mouseenter', 'clusters', function () {
    popup.remove();
  });
  zoomed = true;

  let overpassApiUrl = buildOverpassApiUrl('building', clusterBounds);
  $.get(overpassApiUrl, function (osmDataAsJson) {
    let numBuildings = osmDataAsJson.elements.length;

    if (numBuildings > 2000) {
      // will cause slow behaviour or too-long model run
      $('#map-announce').html('Choose a smaller village!');
      enableClass('run-model', 'disabled');
      setTimeout(resetAnnounce, 2000);
    } else if (numBuildings < 5) {
      // not enough data to work with
      $('#map-announce').html('Choose a village with more buildings!');
      enableClass('run-model', 'disabled');
      setTimeout(resetAnnounce, 2000);
    } else {
      let villageData = osmtogeojson(osmDataAsJson);
      map.getSource('buildings').setData(villageData);
      disableClass('run-model', 'disabled');

      if (passFullVillageGeojson) {
        sliderParams['plan-loc']['village'] = JSON.stringify(villageData);
      }
    }
  });

  updateSliders('plan-loc');

  let colors = layerColors.buildings;
  let labels = {'default': 'Un-modelled', 'mg': 'Mini-grid', 'shs': 'SHS'};
  legendHtml['plan-loc'] = createLegend(colors, labels);

  $('#summary').html(summaryHtml['plan-loc']);
  $('#run-model').html('Run model');
}

/**
 * Build on OSM overpass query based on the bounds and query.
 * 
 * @param {*} overpassQuery 
 * @param {*} bounds 
 */
function buildOverpassApiUrl(overpassQuery, bbox) {
  let west = bbox[0];
  let south = bbox[1];
  let east = bbox[2];
  let north = bbox[3];

  let bounds = south + ', ' + west + ', ' + north + ', ' + east;
  let nodeQuery = 'node[' + overpassQuery + '](' + bounds + ');';
  let wayQuery = 'way[' + overpassQuery + '](' + bounds + ');';
  let relationQuery = 'relation[' + overpassQuery + '](' + bounds + ');';
  let query = '?data=[out:json][timeout:15];(' + nodeQuery + wayQuery + relationQuery + ');out body geom;';
  let baseUrl = 'https://overpass-api.de/api/interpreter';
  let resultUrl = baseUrl + query;
  return resultUrl;
}

/**
 * Zoom out from local to national level,
 * and show appropriate sidebar content.
 */
function zoomToNat() {
  map.flyTo({'zoom': map.getZoom() - 4});

  map.on('mouseenter', 'clusters', mouseOverClusters);
  map.setPaintProperty('clusters', 'fill-opacity', 0.5);

  //disableClass('run-model', 'disabled');
  $('#map-announce').html(clickMsg);
  $('#download-results').html('Download results');

  let state = activeModel == 'plan' ? 'plan-nat' : 'find-nat';
  updateSliders(state);
  $('#legend').html(legendHtml[state]);
  $('#summary').html(summaryHtml[state]);
  if (dynamic) show('dynamic-box');
}

/**
 * Update the left sidebar parametre sliders depnding on the passed params.
 * 
 * @param {*} params 
 */
function updateSliders(state) {
  if (!sliderParams[state]) {
    sliderParams[state] = {};
  }
  let slider_vals = sliderConfigs[state];
  let sliders = $('#sliders');

  sliders.html('');
  for (let name in slider_vals) {
    let vals = slider_vals[name];
    let type = vals.type;
    let def = vals.default;
    let label = vals.label;
    let tooltip = vals.tooltip;
    let unit = vals.unit;
    let min = parseFloat(vals.min);
    let max = parseFloat(vals.max);
    let step = parseFloat(vals.step);
    
    let sliderId = 'sl-' + name;
    let sliderValId = 'sl-' + name + '-val';
    if (!sliderParams[state][name]) {
      sliderParams[state][name] = def;
    }

    let defText;
    if (type == 'range') {
      let defVals = JSON.parse(sliderParams[state][name]);
      defText = defVals[0] + ' - ∞';
    } else {
      defText = sliderParams[state][name];
    }

    sliders.append('<span class="ttip">' + label + ': <span class="ttiptext">' + tooltip + '</span><span id="' + sliderValId + '">' + defText + '</span> ' + unit + '</span>');
    sliders.append('<br><input id="' + sliderId + '" type="text" data-slider-min="' + min + '" data-slider-max="' + max + '" data-slider-step="' + step + '" data-slider-value="' + sliderParams[state][name] + '"/><br>');

    $('#' + sliderId).slider();
    $('#' + sliderId).on('slide', function(slideEvt) {
      let textVal;
      let sliderVal;
      if (type == 'range') {
        let from = slideEvt.value[0];
        let to = slideEvt.value[1];
        let toVal = to;

        if (to == max) {
          to = '∞';
          toVal = 1e19;
        }

        textVal = from + ' - ' + to;
        sliderVal = '[' + from + ',' + toVal + ']';
      } else {
        textVal = slideEvt.value;
        sliderVal = $('#' + sliderId).val();
      }
      $('#' + sliderValId).text(textVal);
      sliderParams[state][name] = sliderVal;

      if (state == 'find-nat') {
        //update map display based on sliders!
        hideClusters();
      }
    });
  }
}

/**
 * 
 */
function hideClusters() {
  let params = sliderParams['find-nat'];

  let pop = JSON.parse(params['pop-range']);
  let grid = JSON.parse(params['grid-range']);
  let ntl = JSON.parse(params['ntl-range']);
  let gdp = JSON.parse(params['gdp-range']);
  let travel = JSON.parse(params['travel-range']);

  let hiddenFilters = [
    'all',
    ['>=', 'pop', pop[0]],
    ['<=', 'pop', pop[1]],
    ['>=', 'grid', grid[0]],
    ['<=', 'grid', grid[1]],
    ['>=', 'ntl', ntl[0]],
    ['<=', 'ntl', ntl[1]],
    ['>=', 'gdp', gdp[0]],
    ['<=', 'gdp', gdp[1]],
    ['>=', 'travel', travel[0]],
    ['<=', 'travel', travel[1]]
  ];

  map.setFilter('clusters', hiddenFilters);
  map.setFilter('clusters-outline', hiddenFilters);
}

/**
 * Update summary results in right sidebar.
 * 
 * @param {*} summaryData 
 * @param {*} summaryHtml 
 */
function updateSummary(state, summaryData) {
  let config = summaryConfigs[state];
  let summary = $('#summary');

  summary.html('<h5 class="text">Summary results</h5>');
  summary.append('<p>');
  for (let name in config) {
    let vals = config[name];
    let value = summaryData[name];
    let label = vals.label;
    let unit = vals.unit;

    if (value > 1e9) {
      value = (value / 1e9).toFixed(2);
      unit = 'billion ' + unit;
    } else if (value > 1e6) {
      value = (value / 1e6).toFixed(2);
      unit = 'million ' + unit;
    } else {
      value = value.toFixed(0);
    }
    
    summary.append(label + ': ' + numberWithCommas(value) + ' ' + unit + '<br>');
  }
  summary.append('</p>');

  if (state == 'plan-nat') {
    let chartData = [
      { 'type': 'Densify', 'pop': summaryData['densify-pop'] },
      { 'type': 'Grid', 'pop': summaryData['new-conn-pop'] },
      { 'type': 'Off-grid', 'pop': summaryData['new-og-pop'] }
    ];
    createChart(chartData);
  }
  summaryHtml[state] = summary.html();
}

/**
 * 
 * @param {*} colors 
 * @param {*} labels 
 */
function createLegend(colors, labels) {
  let legend = $('#legend');
  legend.html('<h5 class="text">Map legend</h5>');
  for (let row in colors) {
    let label = labels[row];
    let color = colors[row];
    legend.append('<div><span class="legend-square" style="background-color: ' + color + '"></span><span>' + label + '</span></div>');
  }
  return legend.html();
}

/**
 * Display the main explore screen with map centered.
 */
function chooseCountry() {
  $('body').addClass('colorbg');
  if (!layersAdded) {
    addMapLayers();
    layersAdded = true;
  }
  hide('landing');
  hide('explore');
  hide('about');
  show('countries');

  zoomed = false;
}

/**
 * Called by clicking the 'plan' button.
 */
function plan() {
  activeModel = 'plan';
  zoomed = false;
  activeMode('go-plan');
  $('#run-model').html('Run model');
  //disableClass('run-model', 'disabled');
  updateSliders('plan-nat');

  if (dynamic) show('dynamic-box');

  $('#summary').html(summaryHtml['plan-nat']);
  if (map.getLayer('network')) {
    map.setLayoutProperty('network', 'visibility', 'visible');
  }

  if (map.getLayer('clusters')) {
    map.setPaintProperty('clusters', 'fill-color', clusterStylingPlan);
    map.setPaintProperty('clusters-outline', 'line-color', clusterStylingPlan);
    map.setFilter('clusters', null);
    map.setFilter('clusters-outline', null);
  }

  let colors = layerColors.clustersPlan;
  let labels = {'default': 'Un-modelled', 'densify': 'Densification', 'grid': 'New connections', 'offgrid': 'Off-grid', 'none': 'None'};
  legendHtml['plan-nat'] = createLegend(colors, labels);

  if (!country) {
    chooseCountry();
  } else {
    $('body').removeClass('colorbg');
    hide('landing');
    show('explore');
    hide('about');
    hide('countries');
  }
}

/**
 * Called by the find opportunities button.
 */
function find() {
  activeModel = 'find';
  zoomed = false;
  activeMode('go-find');
  $('#run-model').html('Run model');
  //disableClass('run-model', 'disabled');
  updateSliders('find-nat');

  $('#summary').html(summaryHtml['find-nat']);
  if (map.getLayer('network')) {
    map.setLayoutProperty('network', 'visibility', 'none');
  }

  if (map.getLayer('clusters')) {
    map.setPaintProperty('clusters', 'fill-color', clusterStylingFind);
    map.setPaintProperty('clusters-outline', 'line-color', clusterStylingFind);
    hideClusters();
  }

  let colors = layerColors.clustersFind;
  let labels = {'default': 'Un-modelled', 'bottom': 'Low priority', 'top': 'High priority'};
  legendHtml['find-nat'] = createLegend(colors, labels);

  if (!country) {
    chooseCountry();
  } else {
    $('body').removeClass('colorbg');
    hide('landing');
    show('explore');
    hide('dynamic-box');
    hide('about');
    hide('countries');
  }
}

let firstRun = true;
/**
 * 
 */
function explore() {
  $('body').removeClass('colorbg');
  if (typeof this !== 'undefined') {
    country = this.id;
  }
  hide('dynamic-box');

  $('#loading-bar').modal('show');
  if (firstRun) {
    //$('#loading-message').html('Warming up the engines.');
    firstRun = false;
  }

  $.ajax({
    url: dataloc + country + '/grid.geojson',
    success: function(data) {
      if (typeof data == 'string') {
        data = JSON.parse(data);
      }
      map.getSource('grid').setData(data);
    },
    error: function() {
      show('server-offline');
      $('#loading-bar').modal('hide');
      $('#loading-message').html('');
    }
  });

  $.ajax({
    url: dataloc + country + '/clusters.geojson',
    success: function(data) {
      if (typeof data == 'string') {
        data = JSON.parse(data);
      }
      map.getSource('clusters').setData(data);
      $('#loading-bar').modal('hide');
      $('#loading-message').html('');
    },
    error: function() {
      show('server-offline');
      $('#loading-bar').modal('hide');
      $('#loading-message').html('');
    }
  });

  $('#map-announce').html(clickMsg);
  $('.country-name').html(capFirst(country));
  $('#country-overview').html('<h5 class="text">Country overview</h5>');
  let population = (countries[country].pop / 1e6).toFixed(2);
  let accessRate = (countries[country]['access-rate']*100).toFixed(2);
  $('#country-overview').append('<p>Population: ' + numberWithCommas(population) + ' million<br>Access rate: ' + accessRate + ' %');

  countryBounds = countries[country].bounds;
  let camera = map.cameraForBounds(countryBounds, {padding: -200});
  map.jumpTo(camera);

  hide('landing');
  show('explore');
  hide('about');
  hide('countries');

  map.resize();
}

/**
 * Display the home page.
 */
function home() {
  $('body').addClass('colorbg');
  activeMode();
  show('landing');
  hide('explore');
  hide('about');
  hide('countries');
}

/**
 * Display the about page.
 */
function about() {
  $('body').addClass('colorbg');
  activeMode();
  hide('landing');
  hide('explore');
  show('about');
  hide('countries');
}

/**
 * Reset announce box after a warning message.
 */
function resetAnnounce() {
  $('#map-announce').html(clickBtn);
  $('#btn-zoom-out').click(zoomToNat);
}

/**
 * Enable/disable buttons depending on mode.
 * 
 * @param {*} mode 
 */
function activeMode(mode) {
  if (mode) {
    let other = mode == 'go-find' ? 'go-plan' : 'go-find';
    enableClass(mode, 'btn-primary');
    disableClass(mode, 'btn-secondary');
    enableClass(other, 'btn-secondary');
    disableClass(other, 'btn-primary');
  } else {
    disableClass('go-plan', 'btn-secondary');
    disableClass('go-find', 'btn-secondary');
    enableClass('go-plan', 'btn-primary');
    enableClass('go-find', 'btn-primary');
  }
}

/**
 * Hide an element by enabling the 'hidden' class.
 * 
 * @param {*} elementId 
 */
function hide(elementId) {
  enableClass(elementId, 'hidden');
}

/**
 * Show a class by removing the 'hidden' class.
 * 
 * @param {*} elementId 
 */
function show(elementId) {
  disableClass(elementId, 'hidden');
}

/**
 * Enable the given class on the given element.
 * 
 * @param {*} elementId 
 * @param {*} className 
 */
function enableClass(elementId, className) {
  let element = document.getElementById(elementId);
  if (!element.classList.contains(className)) {
    element.classList.add(className);
  }
}

/**
 * Disable the given class on the given element.
 * 
 * @param {*} elementId 
 * @param {*} className 
 */
function disableClass(elementId, className) {
  let element = document.getElementById(elementId);
  if (element.classList.contains(className)) {
    element.classList.remove(className);
  }
}

/**
 * 
 * @param {*} r 
 */
function importImages(r) {
  let images = {};
  r.keys().map((item) => { images[item.replace('./', '')] = r(item); });
  return images;
}

/**
 * 
 * @param {*} string 
 */
function capFirst(string) {
  return string.charAt(0).toUpperCase() + string.slice(1);
}

/**
 * 
 * @param {*} dataset 
 */
function createChart(dataset) {
  // TODO make responsive
  var outerWidth = 200;
  var outerHeight = 180;
  var margin = { left: 50, top: 20, right: 0, bottom: 30 };
  var barPadding = 0.2;

  var xColumn = 'type';
  var yColumn = 'pop';
  var colorColumn = 'type';

  function colorPicker(type) {
    if (type == 'Densify') {
      return layerColors.clustersPlan.densify;
    } else if (type == 'Grid') {
      return layerColors.clustersPlan.grid;
    } else {
      return layerColors.clustersPlan.offgrid;
    }
  }

  var innerWidth  = outerWidth  - margin.left - margin.right;
  var innerHeight = outerHeight - margin.top  - margin.bottom;
  
  $('#summary').append('<hp class="text font-weight-bold">Newly connected population</hp>');

  var svg = d3.select('#summary').append('svg')
    .attr('width', '100%')
    .attr('height', outerHeight);

  var g = svg.append('g')
    .attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');
  var xAxisG = g.append('g')
    .attr('class', 'x axis')
    .attr('transform', 'translate(0,' + innerHeight + ')');
  var yAxisG = g.append('g')
    .attr('class', 'y axis');

  var xScale = d3.scale.ordinal().rangeBands([0, innerWidth], barPadding);
  var yScale = d3.scale.linear().range([innerHeight, 0]);

  var xAxis = d3.svg.axis().scale(xScale).orient('bottom')
    .outerTickSize(0);
  var yAxis = d3.svg.axis().scale(yScale).orient('left')
    .ticks(3)
    .tickFormat(d3.format('s'))
    .outerTickSize(0);

  xScale.domain(dataset.map( function (d){ return d[xColumn]; }));
  yScale.domain([0, d3.max(dataset, function (d){ return d[yColumn]; })]);

  xAxisG
    .call(xAxis)
    .selectAll('text')
    .style('font-size', '14px')
    .attr('dx', '-0.4em')
    .attr('dy', '0.8em')
    .attr('transform', 'rotate(-16)' );

  yAxisG
    .call(yAxis)
    .style('font-size', '14px');

  var bars = g.selectAll('rect').data(dataset);
  bars.enter().append('rect')
    .attr('width', xScale.rangeBand());
  bars
    .attr('x', function (d){ return xScale(d[xColumn]); })
    .attr('y', function (d){ return yScale(d[yColumn]); })
    .attr('height', function (d){ return innerHeight - yScale(d[yColumn]); })
    .attr('fill', function (d){ return colorPicker(d[colorColumn]); });
  bars.exit().remove();
}

function numberWithCommas(x) {
  return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * 
 */
function createLayerSwitcher() {
  let toggleableLayerIds = [
    {
      'id': 'streets',
      'name': 'Standard'
    },
    {
      'id': 'satellite',
      'name': 'Satellite'
    }
  ];

  for (let row in toggleableLayerIds) {
    let id = toggleableLayerIds[row].id;
    let name = toggleableLayerIds[row].name;

    let link = document.createElement('a');
    link.href = '#';
    if (id == 'streets') {
      link.className = 'active';
    }
    link.id = id;
    link.textContent = name;

    link.onclick = function (e) {
      e.preventDefault();
      e.stopPropagation();

      let clickedId = e.target.id;
      let otherId = clickedId == 'streets' ? 'satellite' : 'streets';
      let visibility = clickedId == 'streets' ? 'none' : 'visible';

      map.setLayoutProperty(satelliteLayer, 'visibility', visibility);
      document.getElementById(clickedId).className = 'active';
      document.getElementById(otherId).className = '';
    };

    var layers = document.getElementById('baseToggle');
    layers.appendChild(link);
  }
}

function downloadResults() {
  let zip = new JSZip();
  let name;
  
  if (zoomed) { // download buildings
    name = 'local_plan_' + country + '_bounds_' + clusterBounds[0] + '.zip';
    zip.file('buildings.geojson', JSON.stringify(map.getSource('buildings')._data));
    if (map.getSource('lv')) zip.file('lv.geojson', JSON.stringify(map.getSource('lv')._data));
    zip.file('summary.html', summaryHtml['plan-loc']);
  } else { // download clusters
    name = 'nat_' + activeModel + '_' + country + '.zip';
    zip.file('clusters.geojson', JSON.stringify(map.getSource('clusters')._data));
    if (activeModel == 'plan') {
      if (map.getSource('network')) zip.file('network.geojson', JSON.stringify(map.getSource('network')._data));
    }
    let activeSummary = activeModel == 'plan' ? 'plan-nat' : 'find-nat';
    zip.file('summary.html', summaryHtml[activeSummary]);
  }  

  zip.generateAsync({type:'base64'}).then(function (base64) {
    let download = document.getElementById('hiddenDownload');
    download.href='data:application/zip;base64,' + base64;
    download.target = '_blank';
    download.download = name;
    download.click();
  });
}
