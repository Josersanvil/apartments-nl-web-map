import logging
from pathlib import Path
from typing import Any

import folium
import jinja2
from folium.plugins import MarkerCluster

ROOT_APP_FOLDER = Path(__file__).parent.parent
STATIC_FOLDER = ROOT_APP_FOLDER / "static"

OFFICE_COORDS = {"lat": 52.3152336, "lng": 4.9498692}
OFFICE_ADDRESS = "Bijlmerdreef 106, 1102 CT Amsterdam, Netherlands"
OFFICE_NAME = "ING Cedar Office"


def calculate_average_apartments_coords(
    apartments: list[dict[str, Any]]
) -> dict[str, float]:
    """
    Calculates the average coordinates of the apartments.
    """
    latitudes = []
    longitudes = []
    for apartment in apartments:
        coordinates = apartment.get("coordinates")
        if not coordinates:
            continue
        latitudes.append(coordinates["lat"])
        longitudes.append(coordinates["lng"])
    return {
        "lat": sum(latitudes) / len(latitudes),
        "lng": sum(longitudes) / len(longitudes),
    }


def get_logger() -> logging.Logger:
    return logging.getLogger(f"app.map_generator")


def get_gmaps_directions_url(a_coords: dict[str, float], b_coords: dict[str, float]):
    """ "
    Returns the google maps directions url between two locations.
    """
    a_coords_str = ",".join(map(str, a_coords.values()))
    b_coords_str = ",".join(map(str, b_coords.values()))
    return f"https://www.google.com/maps/dir/{a_coords_str}/{b_coords_str}/data=!4m2!4m1!3e3"


def generate_map_html(
    apartments: list[dict[str, Any]], custom_markers: list[dict[str, Any]] = []
) -> str:
    """
    Generates a map representation of the apartments in the dataframe
    as an HTML string.
    """
    logger = get_logger()
    logger.info("Generating map...")
    office_coords = OFFICE_COORDS
    avg_coords = calculate_average_apartments_coords(apartments)
    start_location = (avg_coords["lat"], avg_coords["lng"])
    m = folium.Map(location=start_location, zoom_start=11)
    # if the points are too close to each other, cluster them, create a cluster overlay with MarkerCluster
    marker_cluster = MarkerCluster().add_to(m)
    # draw the markers and assign popup and hover texts
    # add the markers the the cluster layers so that they are automatically clustered
    markers = {}
    for idx, apartment in enumerate(apartments):
        coordinates = apartment.get("coordinates")
        if not coordinates:
            logger.warning(
                f"Apartment '{apartment['title']}' in idx {idx} has no coordinates, skipping..."
            )
            continue
        location = [coordinates["lat"], coordinates["lng"]]
        name = apartment["title"]
        open_new_tab_html = 'target="_blank" rel="noopener noreferrer"'
        btn_style_part = (
            "background-color: #4CAF50; border: none; color: white;"
            "text-align: center; text-decoration: none; display: inline-block;"
        )
        btn_click_part = (
            "onMouseOver=\"this.style.color='yellow'\" "
            "onMouseOut=\"this.style.color='white'\""
        )
        custom_markers_html = ""
        for cm in custom_markers:
            custom_marker_coords = {
                "lat": cm["lat"],
                "lng": cm["lng"],
            }
            custom_marker_directions_url = get_gmaps_directions_url(
                coordinates, custom_marker_coords
            )
            custom_marker_html = (
                f"<a href='{custom_marker_directions_url}' {open_new_tab_html}>"
                f"Directions to '{cm['name']}'</a><br>"
            )
            custom_markers_html += custom_marker_html
        button_style = f'style="{btn_style_part}" {btn_click_part}'
        details = f"""
        <div id="_apt_{idx}">
        <a href={apartment['url']} {open_new_tab_html}><img src="{apartment["thumbnail"]}" width="150px" style="max-height: 125px; object-fit: cover"></a><br>
        <a href={apartment['url']} {open_new_tab_html} style='font-weight: bold'>{apartment['title']}</a><br>
        <small>{apartment['address']}</small><br>
        <br>

        💸 Price: <b>{apartment["price"]}€ per {apartment["price_period"]}</b><br>
        🧱 Surface: {apartment["surface_area_amount"]} {apartment["surface_area_unit"]}<br>
        🛋️ {apartment["interior_type"]}<br>
        {str(int(float(apartment["n_rooms"])))+" Rooms<br>" if apartment["n_rooms"] else ""}
        <br>
        
        🚂 {apartment["time_to_office"]} from office*<br>
        <a href="{apartment["office_directions_url"]}" {open_new_tab_html}>Directions to office</a><br>
        🚂 {apartment["time_to_center"]} from city center*<br>
        <a href="{apartment["center_directions_url"]}" {open_new_tab_html}>Directions to city center</a><br>
        <br>

        {custom_markers_html + '<br>' if custom_markers_html else ''}

        <small>
        * est. time by public transport<br>
        First seen at: {apartment["first_seen_at"].date().isoformat()}<br>
        Last seen at: {apartment["last_seen_at"].date().isoformat()}<br>
        </small>

        <div style="display: flex; gap: 10px; margin-top: 10px;">
            <button {button_style} onclick="markVisited({idx})">Mark visited</button>
            <button {button_style} onclick="markFavorite({idx})">Mark favorite</button>
        </div>
        <div style="display: flex; justify-content: center; margin-top: 5px; margin-bottom: 10px;">
            <button style="{btn_style_part}; width: 100%;" {btn_click_part} onclick="setDefaultColor({idx})">Reset</button>
        </div>
        </div>
        """
        marker = folium.Marker(
            location=location,
            popup=details,
            tooltip=name,
            icon=folium.Icon(color="blue", icon="home"),
        )
        markers[idx] = marker.get_name()
        marker.add_to(marker_cluster)
        marker.icon.options["extraClasses"] += f" _apt_{idx}_marker_icon"
    # Add office marker
    office_location = (office_coords["lat"], office_coords["lng"])
    folium.Marker(
        location=office_location,
        tooltip="ING Cedar Office",
        popup=f"<b>ING Cedar Office</b><br>{OFFICE_ADDRESS}",
        icon=folium.Icon(color="orange", icon="building", prefix="fa"),
    ).add_to(m)
    if custom_markers:
        for cm in custom_markers:
            folium.Marker(
                location=(cm["lat"], cm["lng"]),
                tooltip=cm["name"],
                popup=f"<b>{cm['name']}</b><br><small>Custom marker</small>",
                icon=folium.Icon(color="cadetblue", icon="user", prefix="fa"),
            ).add_to(m)
    # Add macro to change the color of the marker on click of a button
    el = folium.MacroElement().add_to(m)
    with open(STATIC_FOLDER / "scripts.js") as f:
        scripts_body = f.read()
    with open(STATIC_FOLDER / "body.html") as f:
        body = f.read()
    el._template = jinja2.Template(
        f"""
        {{% macro script(this, kwargs) %}}
            ALL_MARKERS = { markers };
            MAP_MARKERS_CLUSTER_NAME = '{ marker_cluster.get_name() }';
            MAP_NAME = '{ m.get_name() }';
            MAX_APARTMENT_PRICE = 3500;
            {scripts_body}
        {{% endmacro %}}
        """
        f"""
        {{% macro html(this, kwargs) %}}
            {body}
        {{% endmacro %}}
        """
    )
    with open("map.html", "w") as f:
        f.write(m._repr_html_())
    return m.get_root().render()
