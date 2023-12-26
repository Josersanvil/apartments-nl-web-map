import io
import os
import sys
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import urlencode

import boto3
import polars as pl
import streamlit as st
import streamlit.components.v1 as components

sys.path.append(str(Path(__file__).parent.parent))
from backend.handler import generate_map_html

st.set_page_config(
    page_title="Apartments in The Netherlands",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/Josersanvil/apartments-nl-web-map/discussions",
        "Report a bug": "https://github.com/Josersanvil/apartments-nl-web-map/issues/new",
        "About": "See https://github.com/Josersanvil/apartments-nl-web-map",
    },
)


def get_query_params() -> dict[str, Any]:
    query_params = st.experimental_get_query_params()
    return query_params


def retrieve_apartments_data() -> BinaryIO:
    """
    Retrieves the apartments data from local or s3
    and returns it as a file-like object.
    """
    apartments_path = os.getenv("APARTMENTS_DATASET_URI")
    if not apartments_path:
        raise ValueError(
            "The path to the apartments dataset is not set. Please set the 'APARTMENTS_DATASET_URI' environment variable."
        )
    fb = io.BytesIO()
    if apartments_path.startswith("s3://"):
        s3_bucket, s3_key = apartments_path.replace("s3://", "").split("/", 1)
        s3 = boto3.client("s3")
        s3.download_fileobj(s3_bucket, s3_key, fb)
        fb.seek(0)
    else:
        # Assume local path
        with open(apartments_path, "rb") as f:
            fb.write(f.read())
        fb.seek(0)
    return fb


def export_filters_url(filters_query_params: dict[str, Any]) -> str:
    """
    Exports the selected filters as a url.
    """
    hostname = os.getenv("APARTMENTS_WEB_HOSTNAME", "localhost:8501")
    if not hostname.startswith("http"):
        hostname = f"http://{hostname}"
    url_params = urlencode(filters_query_params, doseq=True)
    url = f"{hostname}?{url_params}"
    return url


def parse_query_params(query_params: dict[str, Any]) -> dict[str, Any]:
    """
    Parses the query params from the given dictionary.
    """
    array_params = ["city", "interior_type"]
    int_params = ["max_price", "min_surface", "max_days_online"]
    float_params = ["custom_marker_lat", "custom_marker_lng"]
    str_params = ["custom_marker_name"]
    parsed_query_params = {}
    for key, value in query_params.items():
        p_value = value[0] if key not in array_params else value
        if key in array_params:
            parsed_query_params[key] = p_value
        if key in int_params:
            parsed_query_params[key] = int(p_value)
        if key in float_params:
            parsed_query_params[key] = float(p_value)
        if key in str_params:
            parsed_query_params[key] = str(p_value)
    return parsed_query_params


def parse_apartments_dataset(apartments_fb: BinaryIO) -> pl.DataFrame:
    """
    Parses the apartments dataset from the given file-like object
    and returns it as a polars dataframe.
    """
    apartments_data_format = os.getenv("APARTMENTS_DATASET_FORMAT", "parquet")
    if apartments_data_format == "parquet":
        return pl.read_parquet(apartments_fb)
    elif apartments_data_format == "csv":
        return pl.read_csv(apartments_fb)
    else:
        raise ValueError(
            f"Invalid apartments data format '{apartments_data_format}'. Valid are 'parquet' or 'csv'."
        )


@st.cache_data
def get_apartments_max_limit() -> int:
    """
    Returns the maximum number of apartments to show.
    """
    max_apartments_value = os.getenv("APARTMENTS_MAX_ENTRIES", "500")
    if not max_apartments_value.isdigit():
        raise ValueError(
            f"The environment variable 'APARTMENTS_MAX_ENTRIES' should be a number, but is '{max_apartments_value}'."
        )
    return int(max_apartments_value)


@st.cache_data
def load_apartments() -> pl.DataFrame:
    """
    Loads the apartments dataset from local or s3.
    """
    apartments_fb = retrieve_apartments_data()
    apartments = parse_apartments_dataset(apartments_fb)
    return apartments


def update_params_on_change():
    """
    Updates the query params when the filters are changed.
    """
    params = {
        "city": st.session_state.city,
        "max_price": st.session_state.max_price,
        "min_surface": st.session_state.min_surface,
        "interior_type": st.session_state.interior_type,
        "max_days_online": st.session_state.max_days_online,
    }
    if st.session_state.custom_marker_name:
        params["custom_marker_name"] = st.session_state.custom_marker_name
    if st.session_state.custom_marker_lat:
        params["custom_marker_lat"] = st.session_state.custom_marker_lat
    if st.session_state.custom_marker_lng:
        params["custom_marker_lng"] = st.session_state.custom_marker_lng
    st.experimental_set_query_params(**params)


st.title("Apartments in The Netherlands")
raw_apartments = load_apartments()
apartments = raw_apartments.with_columns(
    interior_type=(
        pl.when(raw_apartments["interior_type"].is_null())
        .then(pl.lit("?"))
        .otherwise(raw_apartments["interior_type"])
    ),
    last_seen_at=raw_apartments["last_seen_at"].str.to_datetime("%Y-%m-%d %H:%M:%S%.f"),
    first_seen_at=raw_apartments["first_seen_at"].str.to_datetime(
        "%Y-%m-%d %H:%M:%S%.f"
    ),
)
apartments = apartments.with_columns(
    days_online=(
        apartments["last_seen_at"] - apartments["first_seen_at"]
    ).dt.total_days()
)

OFFICE_NAME = os.getenv("APARTMENTS_MAP_OFFICE_NAME", "the Office")
with st.expander("ℹ️ About", expanded=False):
    st.info(
        f"""
        This map shows apartments that are for rent in some cities in The Netherlands and the distance
        to their respective city center and to {OFFICE_NAME}.

        The apartments are scraped from the following websites:
        - [Pararius](https://www.pararius.com/)

        The apartments can also be marked as favorite (purple) or visited (red) in the map to keep track of them.
        
        Use the filters on the sidebar (left) to filter the apartments on the map or add a custom marker.

        Happy apartment hunting! 🏠
        """
    )

max_value_price = 3500
# Parse query params
query_params = get_query_params()
parsed_query_params = parse_query_params(query_params)
with st.sidebar:
    st.warning(
        "⚠️ Applying filters or changing the custom marker will reset the map, including "
        "visited and favorited apartments."
    )
    st.header("Add filters", help="Filter the apartments on the map.")
    # Warn that adding filters will remove the custom markers
    with st.form("filters_form", border=False):
        # City Filter
        possible_cities = [
            "Amsterdam",
            "Den Haag",
            "Haarlem",
            "Leiden",
            "Rotterdam",
            "Utrecht",
        ]
        selected_cities = st.multiselect(
            "City",
            possible_cities,
            key="city",
            default=parsed_query_params.get("city", possible_cities),
        )
        # Max price filter
        max_price = st.slider(
            "Max price",
            min_value=0,
            max_value=max_value_price,
            value=parsed_query_params.get("max_price", max_value_price),
            key="max_price",
            step=50,
        )
        # Min surface filter
        min_surface = st.slider(
            "Min surface",
            min_value=0,
            max_value=250,
            step=5,
            value=parsed_query_params.get("min_surface", 0),
            key="min_surface",
        )
        # Interior type filter
        possible_interior_types = [
            "furnished",
            "unfurnished",
            "part-furnished",
            "shell",
        ]
        possible_interior_types_title = list(map(str.title, possible_interior_types))
        selected_interior_types = st.multiselect(
            "Interior type",
            possible_interior_types_title,
            default=parsed_query_params.get(
                "interior_type", possible_interior_types_title
            ),
            key="interior_type",
        )
        # Filter days online
        max_days_online = st.slider(
            "Max days online",
            min_value=0,
            max_value=60,
            step=1,
            value=parsed_query_params.get("max_days_online", 60),
            key="max_days_online",
        )
        filters_submit = st.form_submit_button(
            "Apply filters", on_click=update_params_on_change
        )
    st.divider()
    # Custom markers
    st.header(
        "Add a custom marker",
        help="Add the coordinates of a place to add a custom marker on the map.",
    )
    with st.form("custom_markers_form", border=False):
        custom_marker_name = st.text_input(
            "Name",
            value=parsed_query_params.get("custom_marker_name"),
            key="custom_marker_name",
        )
        custom_marker_lat = st.number_input(
            "Latitude",
            value=parsed_query_params.get("custom_marker_lat"),
            key="custom_marker_lat",
        )
        custom_marker_lng = st.number_input(
            "Longitude",
            value=parsed_query_params.get("custom_marker_lng"),
            key="custom_marker_lng",
        )
        marker_submit = st.form_submit_button(
            "Add custom marker", on_click=update_params_on_change
        )
        if marker_submit and not all(
            [custom_marker_name, custom_marker_lat, custom_marker_lng]
        ):
            st.error("Ups! You forgot to fill one of the fields.", icon="🙈")

# Filter apartments based on the filters
filtered_apartments = apartments
selected_cities_internal_names = list(
    map(
        lambda city: city.lower().replace(" ", "-"),
        selected_cities,
    )
)
# Filter apartments
filtered_apartments = filtered_apartments.filter(
    (apartments["city"].str.to_lowercase().is_in(selected_cities_internal_names))
    & (apartments["price"] <= max_price)
    & (apartments["surface_area_amount"] >= min_surface)
    & (
        (
            apartments["interior_type"]
            .str.to_lowercase()
            .is_in(list(map(str.lower, selected_interior_types)))
        )
        | ~apartments["interior_type"].str.to_lowercase().is_in(possible_interior_types)
        | (apartments["interior_type"] == "")
    )
    & (apartments["days_online"] <= max_days_online)
).limit(get_apartments_max_limit())
apartments_to_show = filtered_apartments.to_dicts()
custom_marker = (
    {
        "name": custom_marker_name,
        "lat": custom_marker_lat,
        "lng": custom_marker_lng,
    }
    if all([custom_marker_name, custom_marker_lat, custom_marker_lng])
    else None
)
map_html = generate_map_html(
    apartments_to_show,
    custom_markers=[custom_marker] if custom_marker else [],
)
# Remove strange characters from the html
map_html = map_html.encode("ascii", "ignore").decode("ascii")
# Add iframe:
components.html(map_html, width=None, height=600)
st.text(
    f"Showing {len(apartments_to_show)} apartments (max {get_apartments_max_limit()})."
    if apartments_to_show
    else ":red[No apartments found]"
)
if len(apartments_to_show) == get_apartments_max_limit():
    st.write(
        f":red[Showing the maximum number of apartments ({get_apartments_max_limit()}). Try to apply some filters to see more relevant apartments for you.]"
    )
