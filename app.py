import streamlit as st
import pandas as pd
import pymongo
import pydeck as pdk

st.title('PA State Park 🌧️ Watch')

WEEKEND_DAY_NAMES = ['Friday', 'Saturday', 'Sunday']

#Follow connecting to mongo instructions: https://docs.streamlit.io/knowledge-base/tutorials/databases/mongodb
# Initialize connection.
# Uses st.experimental_singleton to only run once.
@st.experimental_singleton
def init_connection():
    return pymongo.MongoClient(st.secrets["DB_URI"])

client = init_connection()

# Pull data from the collection.
# Uses st.experimental_memo to only rerun when the query changes or after 10 min.
@st.experimental_memo(ttl=600)
def get_data():
    db = client.get_database('PaStateParksDB')
    #items = db.Park.find()
    items =  db.Park.aggregate( [ { "$unwind" : "$daily_forecast" } ] )
    items = list(items)  # make hashable for st.experimental_memo
    return items

def pivot_df(df, dates):
    unused_columns = df.columns.difference(set(['name', 'lat', 'lon', 'miles_from_pgh']).union(set(['date'])).union(set({'chance_precipitation'})))
    tmp_df = df.drop(unused_columns, axis=1)
    pivot_table = tmp_df.pivot_table(
        index=['name', 'lat', 'lon', 'miles_from_pgh'],
        columns=['date'],
        values=['chance_precipitation'],
        aggfunc={'chance_precipitation': ['min']}
    )
    pivot_table.set_axis([col for col in pivot_table.keys()], axis=1, inplace=True)
    pivot_table = pivot_table.reset_index()
    # for col in pivot_table.columns:
    #     try:
    #         if col.startswith("('chance_precip"):
    #             pivot_table.rename(columns={col:' '.join(col.split(' ')[:-2])}, inplace=True)
    #     except:
    #         pass
    return pivot_table

documents = get_data()

raw_data = [(doc['name'], doc['latitude'], doc['longitude'], doc['distance'], doc['daily_forecast']['date'], doc['daily_forecast']['chance_of_precipitation'] )for doc in documents]

long_df = pd.DataFrame(raw_data,
     columns=['name','lat', 'lon', 'miles_from_pgh', 'date', 'chance_precipitation'])

long_df['one_minus_chance_precipitation'] = long_df['chance_precipitation'].apply(lambda x: 1 - x)

st.image('https://cdn.shopify.com/s/files/1/0700/6373/products/0137-Pennsylvania-State-Parks-Map-Print-natural-earth-1.jpg?v=1573340562')

days_included_in_forecast = list(long_df.date.unique())

COLOR_BREWER_BLUE_SCALE = [
    [240, 249, 232],
    [204, 235, 197],
    [168, 221, 181],
    [123, 204, 196],
    [67, 162, 202],
    [8, 104, 172],
]

COLOR_BREWER_RED_SCALE = [
    [254,240,217],
    [253,212,158],
    [253,187,132],
    [252,141,89],
    [227,74,51],
    [179,0,0],
]

st.header('Highlighted Weather Map')

days_selected = st.multiselect(
     'Days To Watch', options=days_included_in_forecast,
     #Make default behavior that only weekend days are presented on weather map
     default= list(filter(lambda x: (x.split(',')[0] in WEEKEND_DAY_NAMES), days_included_in_forecast)) )

highlight_by = st.radio('Highlight by Relative % Chance of Rain', ['low','high'])

filtered_df = long_df[long_df['date'].isin(days_selected)]

selected_weight = 'one_minus_chance_precipitation' if highlight_by == 'low' else 'chance_precipitation'

selected_color_range = COLOR_BREWER_RED_SCALE if highlight_by == 'low' else COLOR_BREWER_BLUE_SCALE

st.pydeck_chart(pdk.Deck(
     map_style='mapbox://styles/mapbox/light-v9',
     initial_view_state=pdk.ViewState(
         latitude=40.44,
         longitude=-79.9957,
         zoom=7
     ),
     layers=[
         pdk.Layer(
            'HexagonLayer',
            data=filtered_df,
            get_position='[lon, lat]',
            auto_highlight=True,
            radius=2000,
            elevation_scale=4,
            elevation_range=[0, 1000],
            pickable=True,
            extruded=True,
         ),
         pdk.Layer(
             'HeatmapLayer',
             data=filtered_df,
             opacity=0.9,
             get_position='[lon, lat]',
             color_range=selected_color_range,
             aggregation='SUM',
             get_weight=selected_weight
             #get_weight="weight"
         ),
     ],
 ))

st.header('Selected Data')
st.dataframe(pivot_df(filtered_df, days_selected))

st.header("Full Forecast Data")
st.dataframe(long_df)