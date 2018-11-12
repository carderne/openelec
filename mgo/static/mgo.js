var map = L.map("main-map").setView([-5.94, 34.5], 7);

// This is the Carto Positron basemap
var basemap = L.tileLayer("https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="http://cartodb.com/attributions">CartoDB</a>',
    subdomains: "abcd",
    maxZoom: 19
});
basemap.addTo(map);
map.on('click', addGenLocation);

var villages;

$(function() {
    $.ajax({
        url: "/_get_village_list",
        success: function(data) {

            villages = data.villages

            // update selector list with villages
            var select = document.getElementById("village");
            for (var row in data.villages) {
                var option = document.createElement("option");
                option.text = row;
                option.value = row;
                select.add(option); 
            }

           addPoints(data.villages)
        }
    });
});


function addPoints(data) {
    pointGroupLayer = L.layerGroup().addTo(map);

    for(var row in data) {
        var marker = L.marker([data[row].lat, data[row].lng]).addTo(pointGroupLayer);
        marker.bindPopup(row);
    }
}


function showVillage() {
    name = $('select[name="village"]').val()

    lat = villages[name].lat
    lng = villages[name].lng
    map.setView([lat, lng], 17);
    document.getElementById("choose-gen").innerHTML = "Click desired generator location";

    readyForGen = true;
}

var genLat;
var genLng;

var hasGenLocation = false;
var readyForGen = false;
function addGenLocation(e) {
    if (readyForGen && !hasGenLocation) {
        hasGenLocation = true;

        genLat = e.latlng.lat.toFixed(4);
        genLng = e.latlng.lng.toFixed(4);

        var marker = L.marker([genLat, genLng]).addTo(map);
        marker.bindPopup("Generator location");
        var icon = L.AwesomeMarkers.icon({
            icon: "bolt",
            iconColor: "white",
            markerColor: "green",
            prefix: "fa",
        });
        marker.setIcon(icon);

        document.getElementById("choose-gen").innerHTML = "Generator site chosen";
        document.getElementById("param-head").innerHTML = "Choose parameters";

        var table = document.getElementById("param-table");
        table.insertRow(-1).innerHTML = '<td>Min house size <small>(m<sup>2</sup>)</small></td><td><input type="text" name="min-area" value="70" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Demand <small>(kWh/pp/mon)</small></td><td><input type="text" name="demand" value="6" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Tariff <small>($/kWh)</small></td><td><input type="text" name="tariff" value="0.2" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Generator cost <small>($/kW)</small></td><td><input type="text" name="gen-cost" value="1000" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Wire cost <small>($/m)</small></td><td><input type="text" name="cost-wire" value="10" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Connection cost <small>($/house)</small></td><td><input type="text" name="cost-connection" value="100" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Annual Opex <small>(% of Capex)</small></td><td><input type="text" name="opex-ratio" value="1" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Project lifetime <small>(years)</small></td><td><input type="text" name="years" value="10" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Discount rate <small>(%)</small></td><td><input type="text" name="discount-rate" value="6" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Max wire length <small>(m)<small></td><td><input type="text" name="max-length" value="10000" size="5"></td>'

        var run = document.getElementById("run")
        run.innerHTML = '<input type="submit" name="run" value="Run (and be patient)" onclick="runModel()">'
    }
}

var resultsTable;
var networkLayer;
var buildingsLayer;

function runModel() {
    $.ajax({
        url: "/_run_model",
        data: {
            name: $('select[name="village"]').val(),
            gen_lat: genLat,
            gen_lng: genLng,
            min_area: $('input[name="min-area"]').val(),
            demand: $('input[name="demand"]').val(),
            tariff: $('input[name="tariff"]').val(),
            gen_cost: $('input[name="gen-cost"]').val(),
            cost_wire: $('input[name="cost-wire"]').val(),
            cost_connection: $('input[name="cost-connection"]').val(),
            opex_ratio: $('input[name="opex-ratio"]').val(),
            years: $('input[name="years"]').val(),
            discount_rate: $('input[name="discount-rate"]').val(),
            max_length: $('input[name="max-length"]').val()
        },

        success: function(data) {
            var network = data.network;
            var buildings = data.buildings;
            var results = data.results;

            document.getElementById("param-head").innerHTML = "Check your results";

            if (resultsTable) {
                resultsTable.innerHTML = ""
            }

            resultsTable = document.getElementById("results");
            resultsTable.insertRow(-1).innerHTML = "Houses connected: " + results.connected;
            resultsTable.insertRow(-1).innerHTML = "Generator size: " + results.gen_size + " kW";
            resultsTable.insertRow(-1).innerHTML = "Total wire length: " + results.length + " m";
            resultsTable.insertRow(-1).innerHTML = "Capex: $" + results.capex;
            resultsTable.insertRow(-1).innerHTML = "Annual opex: $" + results.opex;
            resultsTable.insertRow(-1).innerHTML = "Annual income: $" + results.income;
            resultsTable.insertRow(-1).innerHTML = "NPV: $" + results.npv;

            if (networkLayer || buildingsLayer) {
                networkLayer.remove();
                buildingsLayer.remove();
            }
            
            networkLayer = L.geoJSON(network).addTo(map);

            maxArea = getMax(buildings, "area")
            buildingsLayer = L.geoJSON(buildings, {
                style: function(feature) {
                    return buildingStyle(feature);
                },
                onEachFeature: function (feature, layer) {
                    layer.on({
                        mouseout: function(e) {
                            e.target.setStyle(buildingStyle(e.target.feature));
                        },
                        mouseover: function(e) {
                            e.target.setStyle(buildingHoverStyle);
                        },
                    });
                }
            }).addTo(map);
        }
    });
}

var maxArea;
buildingHoverStyle = {'fillColor': '#b2e2e2', 'fillOpacity': 0.5, 'color': 'black', 'weight': 3}
function buildingStyle(feature) {
    area = feature.properties.area
    if (area > maxArea*0.8) {fillColor = '#006d2c'}
    else if (area > maxArea*0.6) {fillColor = '#2ca25f'}
    else if (area > maxArea*0.4) {fillColor = '#66c2a4'}
    else if (area > maxArea*0.2) {fillColor = '#b2e2e2'}
    else {fillColor = '#edf8fb'}
    return {'fillColor': fillColor, 'weight': 1, 'color': 'black', 'fillOpacity': 1}
}

function getMax(data, property) {
    var max = 0;
    for (var row in data.features) {
        val = parseInt(data.features[row].properties[property])
        if (val > max)
            max = val;
    }
    return max;
}