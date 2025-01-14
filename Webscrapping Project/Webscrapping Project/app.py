import streamlit as st
import requests
import folium
from streamlit_folium import folium_static
import wikipediaapi
from geopy.distance import geodesic
from bs4 import BeautifulSoup
from textblob import TextBlob
import pandas as pd

# Clé API Google Maps
API_KEY = "AIzaSyDWjZ8QyOYG9zoV7Eqh2iNki5namxjnTd8"

# Facteur d'émission de CO₂ pour une voiture moyenne (g/km)
EMISSION_FACTOR_CAR = 120  # Environ 120 g/km

# Fonction pour trouver des châteaux
def find_castles_near_city(city_name, radius):
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    geocode_params = {
        "address": city_name,
        "key": API_KEY
    }
    geocode_response = requests.get(geocode_url, params=geocode_params)
    geocode_data = geocode_response.json()

    if geocode_data["status"] != "OK":
        st.error(f"Erreur lors du géocodage : {geocode_data.get('error_message', 'Inconnue')}")
        return None, None, []

    location = geocode_data["results"][0]["geometry"]["location"]
    lat, lng = location["lat"], location["lng"]

    places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    places_params = {
        "location": f"{lat},{lng}",
        "radius": radius, 
        "keyword": "château",
        "key": API_KEY
    }
    places_response = requests.get(places_url, params=places_params)
    places_data = places_response.json()

    if places_data["status"] != "OK":
        st.error(f"Erreur lors de la recherche des lieux : {places_data.get('error_message', 'Inconnue')}")
        return lat, lng, []

    castles = []
    for place in places_data["results"]:
        place_id = place["place_id"]

        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {
            "place_id": place_id,
            "fields": "name,formatted_address,website,opening_hours,formatted_phone_number,rating,user_ratings_total,reviews",
            "key": API_KEY
        }
        details_response = requests.get(details_url, params=details_params)
        details_data = details_response.json()

        if details_data["status"] == "OK":
            details = details_data["result"]
            website = details.get("website")
            reviews = details.get("reviews", [])
            if website: 
                castles.append({
                    "name": details.get("name", "Nom inconnu"),
                    "location": place["geometry"]["location"],
                    "address": details.get("formatted_address", "Adresse inconnue"),
                    "website": website,
                    "phone": details.get("formatted_phone_number", "Téléphone non disponible"),
                    "rating": details.get("rating", 0),
                    "user_ratings_total": details.get("user_ratings_total", 0),
                    "reviews": reviews
                })

    return lat, lng, castles

def get_wikipedia_info(castle_name):
    wiki_wiki = wikipediaapi.Wikipedia(
        language='fr',
        user_agent='ChateauExplorer/1.0 (https://example.com/contact; example@example.com)'
    )

    page = wiki_wiki.page(castle_name)

    if not page.exists():
        return None, None 

    description = page.summary.split("\n")[0]

    response = requests.get(page.fullurl)
    soup = BeautifulSoup(response.text, 'html.parser')
    image_tag = soup.find('meta', property='og:image')
    image_url = image_tag['content'] if image_tag else None

    return description, image_url

def calculate_carbon_emission(distance_km):
    return distance_km * EMISSION_FACTOR_CAR / 1000

def analyze_sentiment(reviews):
    sentiments = []
    for review in reviews:
        text = review.get("text", "")
        if text:
            sentiment = TextBlob(text).sentiment.polarity
            sentiments.append(sentiment)

    if sentiments:
        avg_sentiment = sum(sentiments) / len(sentiments)
        if avg_sentiment <= -0.6:
            category = "Très Négatif"
        elif -0.6 < avg_sentiment <= -0.2:
            category = "Négatif"
        elif -0.2 < avg_sentiment <= 0.2:
            category = "Neutre"
        elif 0.2 < avg_sentiment <= 0.6:
            category = "Positif"
        else:
            category = "Très Positif"
        return category, avg_sentiment
    return "Aucune donnée disponible", None

# Fonction pour afficher une carte Folium
def display_castles_on_map(lat, lng, castles):
    m = folium.Map(location=[lat, lng], zoom_start=10)

    for castle in castles:
        castle_lat = castle["location"]["lat"]
        castle_lng = castle["location"]["lng"]

        folium.Marker(
            [castle_lat, castle_lng],
            popup=folium.Popup(f"""
            <b>{castle['name']}</b><br>
            Adresse : {castle['address']}<br>
            Note : {castle['rating']} ⭐ ({castle['user_ratings_total']} avis)<br>
            Site web : <a href="{castle['website']}" target="_blank">{castle['website']}</a><br>
            Téléphone : {castle['phone']}
            """, max_width=300),
            icon=folium.Icon(color="blue")
        ).add_to(m)

    return m

# Application Streamlit
st.title("Explorateur de Châteaux")
st.write("Trouvez des châteaux autour de votre ville, obtenez des informations détaillées et planifiez votre itinéraire.")

city = st.text_input("Entrez votre emplacement (par ex., 'Lyon, France')", value="Lyon, France")
radius = st.slider("Rayon de recherche (en km)", min_value=1, max_value=50, step=1, value=10)

if st.button("Rechercher"):
    with st.spinner("Recherche en cours..."):
        lat, lng, castles = find_castles_near_city(city, radius*1000)

    if castles:
        st.success(f"{len(castles)} châteaux trouvés autour de {city} avec un site web !")

        map_object = display_castles_on_map(lat, lng, castles)
        st.write("### Carte des châteaux")
        folium_static(map_object)

        st.write("### Liste des châteaux")

        for castle in castles:
            st.write(f"### 🏰 {castle['name']}")
            st.write(f"- **Adresse :** {castle['address']}")
            st.write(f"- **Site web :** [Visitez le site officiel]({castle['website']})")
            st.write(f"- **Téléphone :** {castle['phone']}")
            st.write(f"- **Note :** {castle['rating']} ⭐ ({castle['user_ratings_total']} avis)")

            distance_km = geodesic((lat, lng), (castle['location']['lat'], castle['location']['lng'])).kilometers
            carbon_emission = calculate_carbon_emission(distance_km)

            st.write(f"- **Distance :** {distance_km:.2f} km")
            st.write(f"- **Empreinte carbone :** {carbon_emission:.2f} kg CO₂")

            if castle['reviews']:
                sentiment_label, sentiment_score = analyze_sentiment(castle['reviews'])
                st.write(f"- **Sentiment des avis :** {sentiment_label} (score: {sentiment_score:.2f})")
            else:
                st.write("- **Sentiment des avis :** Aucune donnée disponible.")

            description, image_url = get_wikipedia_info(castle['name'])
            if description:
                st.write(f"- **Description :** {description}")
            else:
                st.write("- **Description :** Aucune description disponible sur Wikipédia.")

            if image_url:
                st.image(image_url, caption=castle['name'], use_container_width=True)

            destination_coords = f"{castle['location']['lat']},{castle['location']['lng']}"
            maps_url = f"https://www.google.com/maps/dir/?api=1&origin={city.replace(' ', '+')}&destination={destination_coords}&travelmode=driving"
            st.markdown(f"[📍 Itinéraire vers {castle['name']}]({maps_url})", unsafe_allow_html=True)
    else:
        st.warning("Aucun château trouvé avec un site web pour cette recherche.")
