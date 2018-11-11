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
        table.insertRow(-1).innerHTML = '<td>Min house size <small>(m<sup>2</sup>)</small></td><td><input type="text" name="minimum_area_m2" value="70" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Demand <small>(kWh/pp/mon)</small></td><td><input type="text" name="demand" value="6" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Tariff <small>($/kWh)</small></td><td><input type="text" name="tariff" value="0.2" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Generator cost <small>($/kW)</small></td><td><input type="text" name="gen_cost" value="1000" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Wire cost <small>($/m)</small></td><td><input type="text" name="cost_wire" value="10" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Connection cost <small>($/house)</small></td><td><input type="text" name="cost_connection" value="100" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Annual Opex <small>(% of Capex)</small></td><td><input type="text" name="opex_ratio" value="1" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Project lifetime <small>(years)</small></td><td><input type="text" name="years" value="10" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Discount rate <small>(%)</small></td><td><input type="text" name="discount_rate" value="6" size="5"></td>'
        table.insertRow(-1).innerHTML = '<td>Max wire length <small>(m)<small></td><td><input type="text" name="max_tot_length" value="10000" size="5"></td>'

        var run = document.getElementById("run")
        run.innerHTML = '<input type="submit" name="run" value="Run (and be patient)" onclick="runModel()">'
    }
}

function runModel() {

    //TODO check if model has already been run
    // if so, delete previous summary results, network and buildings

    $.ajax({
        url: "/_run_model",
        data: {
            name: $('select[name="village"]').val(),
            gen_lat: genLat,
            gen_lng: genLng,
            minimum_area_m2: $('input[name="minimum_area_m2"]').val(),
            demand: $('input[name="demand"]').val(),
            tariff: $('input[name="tariff"]').val(),
            gen_cost: $('input[name="gen_cost"]').val(),
            cost_wire: $('input[name="cost_wire"]').val(),
            cost_connection: $('input[name="cost_connection"]').val(),
            opex_ratio: $('input[name="opex_ratio"]').val(),
            years: $('input[name="years"]').val(),
            discount_rate: $('input[name="discount_rate"]').val(),
            max_tot_length: $('input[name="max_tot_length"]').val()
        },

        success: function(data) {
            var network = data.network;
            var buildings = data.buildings;
            var results = data.results;

            document.getElementById("param-head").innerHTML = "Check your results";

            var resultsTable = document.getElementById("results");
            resultsTable.insertRow(-1).innerHTML = "Houses connected: " + results.connected;
            resultsTable.insertRow(-1).innerHTML = "Generator size: " + results.gen_size + " kW";
            resultsTable.insertRow(-1).innerHTML = "Total wire length: " + results.length + " m";
            resultsTable.insertRow(-1).innerHTML = "Capex: $" + results.capex;
            resultsTable.insertRow(-1).innerHTML = "Annual opex: $" + results.opex;
            resultsTable.insertRow(-1).innerHTML = "Annual income: $" + results.income;
            resultsTable.insertRow(-1).innerHTML = "NPV: $" + results.npv;
            
            var geojsonNetwork = {
                "type": "FeatureCollection",
                "features": []
            };
            for (var row in network) {
                geojsonNetwork.features.push({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": network[row]
                    },
                });
            }
            L.geoJSON(geojsonNetwork).addTo(map);

            var geojsonBuildings = {
                "type": "FeatureCollection",
                "features": []
            };
            for (var row in buildings) {
                geojsonBuildings.features.push({
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": buildings[row].coords
                    },
                    "properties": {
                        "income": buildings[row].income
                    }
                });
            }
            L.geoJSON(geojsonBuildings, {
                style: function(feature) {
                    area = feature.properties.area
                    if (area > 300) {fillColor = '#006d2c'}
                    else if (area > 180) {fillColor = '#2ca25f'}
                    else if (area > 100) {fillColor = '#66c2a4'}
                    else if (area > 40) {fillColor = '#b2e2e2'}
                    else {fillColor = '#edf8fb'}
                    return {'fillColor': fillColor, 'weight': 1, 'color': 'black', 'fillOpacity': 1}
                }
            }).addTo(map);
        }
    });
 }
