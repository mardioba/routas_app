# main.py

import tkinter as tk
from tkinter import messagebox, scrolledtext
import folium
from geopy.geocoders import Nominatim
import requests
import json
import webbrowser
import math
from collections import OrderedDict
import os # Importar para verificar existência de arquivo
import polyline

# Importa a chave da API (certifique-se de que config.py esteja no mesmo diretório)
try:
    from config import OPENROUTESERVICE_API_KEY
except ImportError:
    OPENROUTESERVICE_API_KEY = None
    messagebox.showwarning("Aviso", "Arquivo 'config.py' não encontrado ou chave da API ausente. A funcionalidade de traçagem de rota pode ser limitada.")

# DEBUG: Adicione esta linha para verificar se a chave está sendo carregada
print(f"Chave da API carregada: {OPENROUTESERVICE_API_KEY is not None}")

class RotaApp:
    def __init__(self, master):
        self.master = master
        master.title("Planejador de Rota")

        # Configuração da Geocodificação
        self.geolocator = Nominatim(user_agent="rota_app_personalizada")

        # --- Frames da Interface ---
        self.input_frame = tk.LabelFrame(master, text="Entrada da Rota", padx=10, pady=10)
        self.input_frame.pack(padx=10, pady=10, fill="x")

        self.output_frame = tk.LabelFrame(master, text="Resultados da Rota", padx=10, pady=10)
        self.output_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # --- Widgets de Entrada ---
        tk.Label(self.input_frame, text="Origem:").grid(row=0, column=0, sticky="w", pady=2)
        self.origem_entry = tk.Entry(self.input_frame, width=50)
        self.origem_entry.grid(row=0, column=1, pady=2)
        self.origem_entry.insert(0, "Lauro de Freitas, BA") # Exemplo para testes

        tk.Label(self.input_frame, text="Destino:").grid(row=1, column=0, sticky="w", pady=2)
        self.destino_entry = tk.Entry(self.input_frame, width=50)
        self.destino_entry.grid(row=1, column=1, pady=2)
        self.destino_entry.insert(0, "Feira de Santana, BA") # Exemplo para testes

        tk.Button(self.input_frame, text="Traçar Rota", command=self.tracar_rota).grid(row=2, column=0, columnspan=2, pady=10)

        # --- Widgets de Saída ---
        tk.Label(self.output_frame, text="Distância Total:").grid(row=0, column=0, sticky="w", pady=2)
        self.distancia_label = tk.Label(self.output_frame, text="")
        self.distancia_label.grid(row=0, column=1, sticky="w", pady=2)

        tk.Label(self.output_frame, text="Tempo Estimado:").grid(row=1, column=0, sticky="w", pady=2)
        self.tempo_label = tk.Label(self.output_frame, text="")
        self.tempo_label.grid(row=1, column=1, sticky="w", pady=2)

        tk.Label(self.output_frame, text="Paradas Sugeridas:").grid(row=2, column=0, sticky="nw", pady=5)
        self.paradas_text = scrolledtext.ScrolledText(self.output_frame, width=60, height=8, wrap=tk.WORD)
        self.paradas_text.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        tk.Label(self.output_frame, text="Cidades na Rota:").grid(row=4, column=0, sticky="nw", pady=5)
        self.cidades_text = scrolledtext.ScrolledText(self.output_frame, width=60, height=8, wrap=tk.WORD)
        self.cidades_text.grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        tk.Button(self.output_frame, text="Abrir Mapa", command=self.abrir_mapa).grid(row=6, column=0, columnspan=2, pady=10)

        # Configurar redimensionamento do grid
        self.output_frame.grid_rowconfigure(3, weight=1)
        self.output_frame.grid_rowconfigure(5, weight=1)
        self.output_frame.grid_columnconfigure(1, weight=1)

    def geocode_address(self, address):
        print(f"Geocodificando endereço: '{address}'") # DEPURACAO
        try:
            location = self.geolocator.geocode(address)
            if location:
                print(f"Endereço '{address}' geocodificado para: ({location.latitude}, {location.longitude})") # DEPURACAO
                return location.latitude, location.longitude
            else:
                print(f"Não foi possível geocodificar '{address}'. Nenhuma localização encontrada.") # DEPURACAO
                return None
        except Exception as e:
            print(f"Erro na geocodificação de '{address}': {e}") # DEPURACAO
            messagebox.showerror("Erro de Geocodificação", f"Não foi possível geocodificar '{address}': {e}")
            return None

    def reverse_geocode_coords(self, lat, lon):
        try:
            location = self.geolocator.reverse((lat, lon), exactly_one=True)
            if location and location.address:
                address_parts = location.raw.get('address', {})
                city = address_parts.get('city') or \
                       address_parts.get('town') or \
                       address_parts.get('village') or \
                       address_parts.get('county')
                if city:
                    return city
                return location.address.split(',')[0].strip()
            print(f"Local desconhecido para coordenadas: ({lat}, {lon})") # DEPURACAO
            return "Local Desconhecido"
        except Exception as e:
            print(f"Erro ao obter local para ({lat}, {lon}): {e}") # DEPURACAO
            return f"Erro ao obter local: {e}"

    def get_route_from_ors(self, start_coords, end_coords):
        self.paradas_text.delete(1.0, tk.END)
        self.cidades_text.delete(1.0, tk.END)
        if not OPENROUTESERVICE_API_KEY:
            messagebox.showerror("Erro de API", "Chave da API do OpenRouteService não configurada. A traçagem de rota não funcionará.")
            return None

        headers = {
            'Accept': 'application/json, application/geo+json, application/gpx+xml, image/png',
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': OPENROUTESERVICE_API_KEY
        }
        body = {
            "coordinates": [
                [start_coords[1], start_coords[0]],  # ORS espera [longitude, latitude]
                [end_coords[1], end_coords[0]]
            ]
            # REMOVA A LINHA ABAIXO:
            # "geometry_format": "polyline"
        }
        url = 'https://api.openrouteservice.org/v2/directions/driving-car'
        try:
            response = requests.post(url, json=body, headers=headers)
            print(f"Status da Resposta ORS: {response.status_code}")
            print(f"Conteúdo da Resposta ORS: {response.text}")

            response.raise_for_status()
            data = response.json()
            print("Resposta ORS decodificada com sucesso.")
            return data
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível conectar ao OpenRouteService: {e}")
            return None
        except json.JSONDecodeError:
            messagebox.showerror("Erro de Resposta", f"Resposta inválida do OpenRouteService. Não foi possível decodificar JSON. Conteúdo: {response.text}")
            return None
        except Exception as e:
            messagebox.showerror("Erro Inesperado ORS", f"Ocorreu um erro ao obter rota: {e}")
            return None

    def tracar_rota(self):
        self.paradas_text.delete(1.0, tk.END)
        self.cidades_text.delete(1.0, tk.END)
        print("Botão 'Traçar Rota' clicado.") # DEPURACAO
        origem = self.origem_entry.get().strip()
        destino = self.destino_entry.get().strip()

        if not origem or not destino:
            messagebox.showwarning("Entrada Inválida", "Por favor, preencha os campos de origem e destino.")
            return

        print("Campos de saída limpos.") # DEPURACAO
        self.distancia_label.config(text="")
        self.tempo_label.config(text="")
        self.paradas_text.delete(1.0, tk.END)
        self.cidades_text.delete(1.0, tk.END)

        print(f"Geocodificando endereço: '{origem}'") # DEPURACAO
        origem_coords = self.geocode_address(origem)
        if origem_coords:
            print(f"Endereço '{origem}' geocodificado para: {origem_coords}") # DEPURACAO
        print(f"Geocodificando endereço: '{destino}'") # DEPURACAO
        destino_coords = self.geocode_address(destino)
        if destino_coords:
            print(f"Endereço '{destino}' geocodificado para: {destino_coords}") # DEPURACAO
        if not origem_coords or not destino_coords:
            messagebox.showerror("Erro", "Não foi possível encontrar as coordenadas para origem ou destino.")
            return

        print("Chamando get_route_from_ors...") # DEPURACAO
        route_data = self.get_route_from_ors(origem_coords, destino_coords)
        if not route_data:
            return

        print(f"Conteúdo de route_data: {json.dumps(route_data, indent=2)}") # DEPURACAO

        if 'routes' not in route_data or not route_data['routes']:
            messagebox.showerror("Erro de Rota", "Não foi possível obter a rota. Verifique os endereços e sua chave de API. Resposta da API pode não conter rotas.")
            return

        # VERIFICAÇÃO ATUALIZADA AQUI:
        # A geometria vem como string codificada, precisamos decodificá-la
        encoded_geometry = route_data['routes'][0]['geometry']

        if not isinstance(encoded_geometry, str): # Se por algum motivo não for string, avisar
            messagebox.showerror("Erro de Rota", f"A geometria da rota não é uma string codificada como esperado. Tipo: {type(encoded_geometry)}. Conteúdo: {encoded_geometry}")
            return

        try:
            # Decodifica a string Polyline para uma lista de [latitude, longitude]
            route_coords_folium = polyline.decode(encoded_geometry)
        except Exception as e:
            messagebox.showerror("Erro de Decodificação", f"Não foi possível decodificar a geometria da rota: {e}. Conteúdo: {encoded_geometry}")
            return

        distance_meters = route_data['routes'][0]['summary']['distance']
        duration_seconds = route_data['routes'][0]['summary']['duration']

        # Conversão para km e horas/minutos
        distance_km = distance_meters / 1000
        duration_hours = int(duration_seconds / 3600)
        duration_minutes = int((duration_seconds % 3600) / 60)

        self.distancia_label.config(text=f"{distance_km:.2f} km")
        self.tempo_label.config(text=f"{duration_hours}h {duration_minutes}min")

        self.gerar_mapa(origem_coords, destino_coords, route_coords_folium)
        self.sugerir_paradas(route_coords_folium, distance_km)
        self.listar_cidades_na_rota(route_coords_folium)

    def gerar_mapa(self, origem_coords, destino_coords, route_coords_folium):
        print("Gerando mapa...") # DEPURACAO
        if not route_coords_folium:
            print("Rota vazia, mapa não será gerado.") # DEPURACAO
            return

        # Cria um mapa Folium
        m = folium.Map(location=[(origem_coords[0] + destino_coords[0]) / 2,
                                 (origem_coords[1] + destino_coords[1]) / 2],
                       zoom_start=7)

        # Adiciona marcadores de origem e destino
        folium.Marker(location=origem_coords, popup="Origem", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(location=destino_coords, popup="Destino", icon=folium.Icon(color="red")).add_to(m)

        # Adiciona a linha da rota
        folium.PolyLine(route_coords_folium, color="blue", weight=5, opacity=0.7).add_to(m)

        # Salva o mapa em um arquivo HTML temporário
        map_filename = "mapa.html"
        m.save(map_filename)
        print(f"Mapa salvo em {map_filename}.") # DEPURACAO

    def abrir_mapa(self):
        map_filename = "mapa.html"
        if os.path.exists(map_filename):
            print(f"Abrindo mapa: {map_filename}") # DEPURACAO
            try:
                webbrowser.open_new_tab(map_filename)
            except Exception as e:
                messagebox.showerror("Erro ao Abrir Mapa", f"Não foi possível abrir o mapa: {e}")
                print(f"Erro ao abrir mapa via webbrowser: {e}") # DEPURACAO
        else:
            messagebox.showwarning("Mapa Ausente", "O mapa ainda não foi gerado. Por favor, trace a rota primeiro.")
            print("Tentativa de abrir mapa, mas 'mapa.html' não existe.") # DEPURACAO

    def sugerir_paradas(self, route_coords_folium, total_distance_km, interval_km=100):
        self.paradas_text.delete(1.0, tk.END)
        print("Sugerindo paradas...") # DEPURACAO
        paradas_sugeridas = []

        if not route_coords_folium:
            self.paradas_text.insert(tk.END, "Nenhuma rota para sugerir paradas.")
            print("Rota vazia para sugerir paradas.") # DEPURACAO
            return

        # ... (resto da lógica de sugerir_paradas, sem alteração) ...
        path_length_km = 0.0
        for i in range(len(route_coords_folium) - 1):
            lat1, lon1 = route_coords_folium[i]
            lat2, lon2 = route_coords_folium[i+1]
            path_length_km += self._haversine_distance(lat1, lon1, lat2, lon2)

        current_distance_km = 0.0
        next_stop_distance = interval_km

        for i in range(len(route_coords_folium) - 1):
            lat1, lon1 = route_coords_folium[i]
            lat2, lon2 = route_coords_folium[i+1]
            segment_distance_km = self._haversine_distance(lat1, lon1, lat2, lon2)

            while current_distance_km + segment_distance_km >= next_stop_distance:
                # Calcula a proporção do segmento para atingir a próxima parada
                # Evita divisão por zero se segment_distance_km for 0
                if segment_distance_km > 0:
                    remaining_dist_in_segment = next_stop_distance - current_distance_km
                    ratio = remaining_dist_in_segment / segment_distance_km
                else:
                    ratio = 0 # No change if segment length is zero

                # Interpola as coordenadas para encontrar o ponto da parada
                stop_lat = lat1 + ratio * (lat2 - lat1)
                stop_lon = lon1 + ratio * (lon2 - lon1)

                city_name = self.reverse_geocode_coords(stop_lat, stop_lon)
                paradas_sugeridas.append(f"• Aprox. {next_stop_distance:.0f} km: {city_name} ({stop_lat:.4f}, {stop_lon:.4f})")
                next_stop_distance += interval_km

                # Se a próxima parada calculada for maior que a distância total, paramos
                if next_stop_distance > total_distance_km + interval_km/2: # Margem para evitar paradas muito próximas do final
                    break

            current_distance_km += segment_distance_km
            if next_stop_distance > total_distance_km + interval_km/2:
                break # Sai do loop externo também

        if paradas_sugeridas:
            self.paradas_text.insert(tk.END, "\n".join(paradas_sugeridas))
            print(f"Paradas sugeridas preenchidas: {len(paradas_sugeridas)} paradas.") # DEPURACAO
        else:
            self.paradas_text.insert(tk.END, "Nenhuma parada sugerida para a distância.")
            print("Nenhuma parada sugerida.") # DEPURACAO


    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        # ... (sem alteração) ...
        R = 6371  # Raio médio da Terra em quilômetros

        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance

    def listar_cidades_na_rota(self, route_coords_folium, sample_interval_km=20):
        self.cidades_text.delete(1.0, tk.END)
        print("Listando cidades na rota...") # DEPURACAO
        cidades_encontradas = OrderedDict() # Para manter a ordem e evitar duplicatas

        if not route_coords_folium:
            self.cidades_text.insert(tk.END, "Nenhuma rota para listar cidades.")
            print("Rota vazia para listar cidades.") # DEPURACAO
            return

        # ... (resto da lógica de listar_cidades_na_rota, sem alteração) ...
        path_length_km = 0.0
        for i in range(len(route_coords_folium) - 1):
            lat1, lon1 = route_coords_folium[i]
            lat2, lon2 = route_coords_folium[i+1]
            path_length_km += self._haversine_distance(lat1, lon1, lat2, lon2)

        current_distance_km = 0.0
        next_sample_distance = 0.0

        while next_sample_distance <= path_length_km: # Percorre a rota por distância
            # Encontra o ponto na rota correspondente a next_sample_distance
            found_point = False
            segment_start_km = 0.0
            for i in range(len(route_coords_folium) - 1):
                lat1, lon1 = route_coords_folium[i]
                lat2, lon2 = route_coords_folium[i+1]
                segment_distance_km = self._haversine_distance(lat1, lon1, lat2, lon2)

                if segment_start_km + segment_distance_km >= next_sample_distance:
                    # O ponto está neste segmento
                    if segment_distance_km > 0:
                        ratio = (next_sample_distance - segment_start_km) / segment_distance_km
                    else:
                        ratio = 0 # No change if segment length is zero

                    sample_lat = lat1 + ratio * (lat2 - lat1)
                    sample_lon = lon1 + ratio * (lon2 - lon1)

                    city = self.reverse_geocode_coords(sample_lat, sample_lon)
                    if city and "Erro ao obter local" not in city and city not in cidades_encontradas:
                        cidades_encontradas[city] = True
                    found_point = True
                    break
                segment_start_km += segment_distance_km
            
            if not found_point and next_sample_distance > 0: # Caso não encontre (rota muito curta ou erro de cálculo)
                break 

            next_sample_distance += sample_interval_km

        # Adiciona a cidade de destino (se ainda não estiver na lista)
        if route_coords_folium:
            final_lat, final_lon = route_coords_folium[-1]
            final_city = self.reverse_geocode_coords(final_lat, final_lon)
            if final_city and "Erro ao obter local" not in final_city and final_city not in cidades_encontradas:
                cidades_encontradas[final_city] = True


        if cidades_encontradas:
            self.cidades_text.insert(tk.END, "\n".join(cidades_encontradas.keys()))
            print(f"Cidades na rota preenchidas: {len(cidades_encontradas)} cidades.") # DEPURACAO
        else:
            self.cidades_text.insert(tk.END, "Nenhuma cidade encontrada na rota.")
            print("Nenhuma cidade encontrada na rota.") # DEPURACAO

if __name__ == "__main__":
    root = tk.Tk()
    app = RotaApp(root)
    root.mainloop()