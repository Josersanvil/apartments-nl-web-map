function markVisited(markerIdx) {
    var markerName = ALL_MARKERS[markerIdx]
    var marker = window[markerName];
    marker.setIcon(new L.AwesomeMarkers.icon({ icon: 'home', markerColor: 'red' }));
    // Make sure it is in the cluster
    var cluster = window[MAP_MARKERS_CLUSTER_NAME];
    marker.addTo(cluster);
}

function markFavorite(markerIdx) {
    var markerName = ALL_MARKERS[markerIdx]
    var marker = window[markerName];
    marker.setIcon(new L.AwesomeMarkers.icon({ icon: 'star', markerColor: 'purple' }));
    // Remove it from the cluster
    var cluster = window[MAP_MARKERS_CLUSTER_NAME];
    marker.removeFrom(cluster);
    // Add it to the map
    var map = window[MAP_NAME];
    marker.addTo(map);
}

function setDefaultColor(markerIdx) {
    var markerName = ALL_MARKERS[markerIdx]
    var marker = window[markerName];
    marker.setIcon(new L.AwesomeMarkers.icon({ icon: 'home', markerColor: 'blue' }));
    // Make sure it is in the cluster
    var cluster = window[MAP_MARKERS_CLUSTER_NAME];
    marker.addTo(cluster);
}

var map = window[MAP_NAME];
map.addControl(new L.Control.Fullscreen());
