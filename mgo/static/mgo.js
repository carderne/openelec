var map = L.map("map").setView([-5.94, 34.5], 7);

// This is the Carto Positron basemap
var basemap = L.tileLayer("https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="http://cartodb.com/attributions">CartoDB</a>',
    subdomains: "abcd",
    maxZoom: 19
});
basemap.addTo(map);

var villages;

$(function() {
    // $('a#calculate').bind('click', getValue)

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

    //console.log(data)

    pointGroupLayer = L.layerGroup().addTo(map);

    for(var row in data) {
        var marker = L.marker([data[row].lat, data[row].lng]).addTo(pointGroupLayer);
        marker.bindPopup(row);
    }
}

/*
function getValue() {
    $.ajax({
        url: "/_add_numbers",
        data: {
            a: $('input[name="a"]').val(),
            b: $('input[name="b"]').val()
        },
        success: function(data) {
            $("#result").text(data.result);
        }
    });
}
*/

function showVillage() {
    name = $('select[name="village"]').val()

    lat = villages[name].lat
    lng = villages[name].lng

    map.setView([lat, lng], 16);

    //$("#choose-village").text("Click desired generator location");

    document.getElementById("choose-gen").innerHTML = "Click desired generator location";
    //chooseVillage.text = "Click desired generator location"

    map.on('click', function(e) {
        genLoc = "/?lat=" + e.latlng.lat.toFixed(4) + "&lng=" + e.latlng.lng.toFixed(4);
        // create API for gen loc?
        // or just display variable input
    });
}
 