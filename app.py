import json
import logging
import os
import os.path

import requests
import xml.etree.ElementTree as ET

from flask import Flask, jsonify, abort
from flask_cors import CORS
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

DATA_PATH = os.getenv("POSTIME_DATA", "data.json")

HOST = os.getenv("POSTIME_DTS_HOST", "0.0.0.0")
PORT = os.getenv("POSTIME_DTS_PORT", 8080)

GH_USER = os.getenv("POSTIME_GH_USER", "postime")

API_CLIENT = os.getenv("POSTIME_API_CLIENT", "http://localhost:5173")
API_PREFIX = os.getenv("POSTIME_API_PREFIX", "/api").rstrip("/")
DTS_API_PREFIX = os.getenv("POSTIME_DTS_API_PREFIX", "/api/dts").rstrip("/")

SPECS = os.getenv("DTS_SPEC_URL",
                  "https://distributed-text-services.github.io/specifications/context/1-alpha1.json")

def filter_data(data, keys=None, keys_to_remove=None):
    if keys and keys_to_remove:
        raise ValueError("Both keys and keys_to_remove provided")
    return {
        key: val for key, val in data.items()
        if (keys and key in keys)
           or (keys_to_remove and key not in keys_to_remove)
    }

def get_id_from_name(name, prefix):
    return name.removesuffix('.xml').replace(f"prefix_", "").replace('_', ' ')

def parse_xml(url):
    root = None

    try:
        response = requests.get(url)
        root = ET.fromstring(response.text)
    except requests.RequestException as e:
        logging.error(f"Error fetching file {url}: {e}")
        return None
    except ET.ParseError as e:
        logging.error(f"Error parsing file {url}: {e}")

    pages = root.findall(".//{http://www.tei-c.org/ns/1.0}pb") if root else []

    return {
        'firstPage': pages[0].attrib['n'] if len(pages) else None,
        'lastPage': pages[-1].attrib['n'] if len(pages) else None,
        'text': response.text
    }

def load_toolbox(name):
    morph_info = {}
    with open(f"toolbox/{name}", "r") as inp_file:
        values = {}
        cur_id = None

        for line in inp_file:
            line = line.strip()
            if not line.startswith('\\') or ' ' not in line:
                if cur_id:
                    morph_info[cur_id] = values.copy()
                values.clear()
                continue

            marker, value = line.split(' ', 1)
            if marker == '\\ref':
                cur_id = value
            values[marker] = value

    return {'morph': morph_info}

def load_source(user, repo):
    results = []

    gh_api_url = f"https://api.github.com/repos/{user}/{repo}-TEI/contents/"
    response = requests.get(gh_api_url)
    for elem in response.json():
        if not elem['name'].endswith('xml'):
            continue

        morph_info = load_toolbox(elem['name'].replace('.xml', '.txt')) if os.path.exists(f"toolbox/{elem['name'].replace('.xml', '.txt')}") else {}
        xml_info = parse_xml(elem['download_url'])
        if xml_info:
            results.append({
                'id': elem['name'],
                'title': get_id_from_name(elem['name'], repo)
            } | parse_xml(elem['download_url']) | morph_info)

    return results


def load_data(path):
    result = []

    with open(path, "r") as inp_file:
        data = json.load(inp_file)

        for source in data:
            result.append({
                'metadata': {
                    'id': source['id'],
                    'title': source['title'],
                    'description': source['description'],
                },
                'sermons': load_source('postime', source['id'].replace('_', ''))
            })

    return result

data = load_data(DATA_PATH)
data_index = {row['metadata']['id']: row for row in data}

app = Flask(__name__)
cors = CORS(app, resources={
    f"{API_PREFIX}/*": {"origins": API_CLIENT},
    f"{DTS_API_PREFIX}/*": {"origins": "*"},
})


def format_response_dts(data):
    headers = {
        "@context": SPECS,
        "dtsVersion": "1-alpha",
        "@id": API_PREFIX,
        "@type": "EntryPoint",
        "collection": "/dts/api/collection/{?id,page,nav}",
        "navigation" : "/dts/api/navigation/{?resource,ref,start,end,down,tree,page}",
        "document": "/dts/api/document/{?resource,ref,start,end,tree,mediaType}"
    }
    return jsonify(data)


@app.route(API_PREFIX)
@app.route(f"{API_PREFIX}/")
def index():
    return jsonify([source['metadata'] for source in data])

@app.route(f"{API_PREFIX}/<string:source_id>")
@app.route(f"{API_PREFIX}/<string:source_id>/")
def get_source(source_id):
    if source_id not in data_index:
        abort(404)
    cur_source = data_index[source_id]

    return jsonify({
        'metadata': cur_source['metadata'],
        'sermons': [filter_data(sermon, keys_to_remove=('text',)) for sermon in cur_source['sermons']]
    })

@app.route(f"{API_PREFIX}/<string:source_id>/<string:sermon_id>")
@app.route(f"{API_PREFIX}/<string:source_id>/<string:sermon_id>/")
def get_sermon(source_id, sermon_id):
    if source_id not in data_index:
        abort(404)

    for sermon in data_index[source_id]['sermons']:
        if sermon['id'] == sermon_id:
            return jsonify(sermon)

    abort(404)

@app.route(f"{API_PREFIX}/timeline")
@app.route(f"{API_PREFIX}/timeline/")
def get_timeline():
    return open("timeline.json", "r").read()

@app.route(f"{DTS_API_PREFIX}/collection")
def get_collection():
    return jsonify({})

@app.route(f"{DTS_API_PREFIX}/navigation")
def navigation():
    return jsonify({})

@app.route(f"{DTS_API_PREFIX}/document")
def document():
    return jsonify({})

if __name__ == "__main__":
    app.run(host=HOST, port=PORT)