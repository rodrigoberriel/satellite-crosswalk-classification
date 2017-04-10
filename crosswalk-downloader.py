import os
import sys
import time
import json
import requests
import urllib
import threading
import cv2
import math
from scipy.spatial import distance
import logging

key = None
img_size = '200x225'
max_threads = 500
resquest_per_second = 40.0  # limit is 50/sec, up to 2500/day
nb_of_no_crosswalk_foreach_crosswalk = 2.2
get_path_every_n_crosswalks = 1
max_nb_of_waypoints = 20
max_attempts = 5


def log_and_print(message):
    print(message)
    logging.info(message)


def get_crosswalks(region):
    # REQUEST URL
    base_api_osm = 'https://overpass-api.de/api/'
    node_query = '"highway"~"crossing"'
    params = 'interpreter?data=[out:json];node[{}]({});out body;'.format(node_query, ','.join(map(str, region)))
    request_url = base_api_osm + params
    response = requests.get(request_url).json()
    return [{'id': i, 'lat': e['lat'], 'lng': e['lon']} for i, e in enumerate(response['elements'])]


def thread_download_static_map(location, type, region_name):
    base_api_static_maps = 'https://maps.googleapis.com/maps/api/staticmap'
    request_url = '{}?center={}&zoom=20&size={}&maptype=satellite&key={}'.format(
        base_api_static_maps, ','.join(map(str, [location['lat'], location['lng']])), img_size, key
    )
    urllib.urlretrieve(request_url, os.path.join(region_name, type, '{}.png'.format(location['id'])))


def get_directions_polylines(waypoints):
    orig = waypoints[0]
    dest = waypoints[-1]
    orig = '{},{}'.format(orig['lat'], orig['lng'])
    dest = '{},{}'.format(dest['lat'], dest['lng'])
    waypoints_str = '|'.join(['{},{}'.format(w['lat'], w['lng']) for w in waypoints[1:-1]])

    base_api = 'https://maps.googleapis.com/maps/api/directions/json'
    api_params = 'origin={}&destination={}&waypoints={}&key={}'.format(orig, dest, waypoints_str, key)
    request_url = '{}?{}'.format(base_api, api_params)

    polyline_data = {"request_url": request_url, "overview_polyline": ""}
    for nb_attempts in range(max_attempts):
        try:
            response = requests.get(request_url).json()
            polyline_data["overview_polyline"] = response['routes'][0]['overview_polyline']['points']
            break
        except:
            log_and_print('Request #{} to Direction API failed. Trying again...'.format(nb_attempts))
            time.sleep(1.0/max_threads)
    return polyline_data


def download_images(crosswalks, img_type, region_name):
    # get the images of img_type = {crosswalks, no-crosswalks}
    mythreads = []
    total = 0
    for i, crosswalk in enumerate(crosswalks):
        t = threading.Thread(target=thread_download_static_map, args=(crosswalk, img_type, region_name))
        mythreads.append(t)
        t.start()
        if (len(mythreads) >= max_threads) or (i == len(crosswalks) - 1):
            for t in mythreads:
                t.join()
            total += len(mythreads)
            mythreads[:] = []  # clear the thread's list
            log_and_print('Downloaded {} images already...'.format(total))
    log_and_print('Done: downloaded {} images...'.format(total))


def download_polylines_points(crosswalks, region):
    # get the path between these crosswalks
    min_points = int(nb_of_no_crosswalk_foreach_crosswalk * len(crosswalks))

    all_points = []
    no_crosswalk_points = []
    paths_data = []
    nb_duplicates = 0

    nb_of_paths = int(math.ceil((len(crosswalks) - 1) / float((max_nb_of_waypoints + 1))))
    log_and_print('Downloading {} paths from {} crosswalks'.format(nb_of_paths, len(crosswalks)))
    for i in range(nb_of_paths):

        path_start = i*(max_nb_of_waypoints+1)
        path_end = min((i+1)*(max_nb_of_waypoints+1), len(crosswalks)-1)
        waypoints = [crosswalks[j] for j in range(path_start, path_end+1)]

        path_data = get_directions_polylines(waypoints)
        paths_data.append(path_data)

        polylines_points, nb_polylines_duplicates = decode_polylines([path_data['overview_polyline']])
        no_crosswalk_polylines_points = remove_close_to_crosswalk(polylines_points, crosswalks, region)

        all_points.extend(polylines_points)
        no_crosswalk_points.extend(no_crosswalk_polylines_points)
        nb_duplicates += nb_polylines_duplicates

        log_and_print('Got {} points so far. We need at least {}'.format(len(no_crosswalk_points), min_points))
        if len(no_crosswalk_points) > min_points:
            break

    # sets an ID for the no-crosswalks
    for i in range(len(no_crosswalk_points)):
        no_crosswalk_points[i]['id'] = i

    log_and_print('Download of polylines finished! Nb of points: {}'.format(len(no_crosswalk_points)))

    return paths_data, all_points, nb_duplicates, no_crosswalk_points


def save_to_json(content, fname):
    with open(fname, 'w') as hf:
        json.dump(content, hf, indent=4, sort_keys=True)


def decode_polyline(polyline_str):
    """Pass a Google Maps encoded polyline string; returns list of lat/lon pairs"""
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}

    # Coordinates have variable length when encoded, so just keep
    # track of whether we've hit the end of the string. In each
    # while loop iteration, a single coordinate is decoded.
    while index < len(polyline_str):
        # Gather lat/lon changes, store them in a dictionary to apply them later
        for unit in ['latitude', 'longitude']:
            shift, result = 0, 0

            while index < len(polyline_str):
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1f) << shift
                shift += 5
                if not byte >= 0x20:
                    break

            if result & 1:
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = (result >> 1)

        lat += changes['latitude']
        lng += changes['longitude']

        coordinates.append((lat / 100000.0, lng / 100000.0))

    return coordinates


def decode_polylines(polylines):
    all_points = []
    for i, p in enumerate(polylines):
        points_polyline = decode_polyline(p)
        points_polyline = generate_samples_interpoler(points_polyline)
        all_points.extend(points_polyline)
    no_duplicate_points = list(set(all_points))
    return no_duplicate_points, len(all_points) - len(no_duplicate_points)


def remove_close_to_crosswalk(points, crosswalks, region):
    min_dist = 0.0003  # approx 33 meters
    max_dist = 0.0006  # approx 66 meters
    no_crosswalk_points = []
    for i, point in enumerate(points):
        dist_to_crosswalk = get_min_dist_to_crosswalk(point, crosswalks)
        if is_inside_region(point, region, min_dist) and min_dist < dist_to_crosswalk < max_dist:
            no_crosswalk_points.append({'lat': point[0], 'lng': point[1]})
    return no_crosswalk_points


def get_min_dist_to_crosswalk(location, crosswalks):
    min_dist = 360
    for crosswalk in crosswalks:
        dist = distance.euclidean(location, (crosswalk['lat'], crosswalk['lng']))
        if dist < min_dist:
            min_dist = dist
    return min_dist


def is_inside_region(point, region, safe_margin):
    lower_bound = point[0] > (region[0] + safe_margin)
    upper_bound = point[0] < (region[2] - safe_margin)
    left_bound = point[1] > (region[1] + safe_margin)
    right_bound = point[1] < (region[3] - safe_margin)
    return lower_bound and upper_bound and left_bound and right_bound


def generate_samples_interpoler(points):
    max_sample_step = 0.00015  # approx. 16 meters
    new_points = []
    for i in range(len(points) - 1):
        dist = distance.euclidean(points[i], points[i+1])
        num_steps = int(round(dist / max_sample_step))
        num_steps = 1 if num_steps <= 1 else num_steps

        step_size_lat = (points[i+1][0] - points[i][0]) / num_steps
        step_size_lng = (points[i+1][1] - points[i][1]) / num_steps

        for j in range(num_steps):
            new_points.append((points[i][0] + j*step_size_lat, points[i][1] + j*step_size_lng))
        new_points.append(points[i+1])
    return new_points


def crop_images(region_name, download_crosswalks, download_no_crosswalks):
    deleted_files = 0
    if download_crosswalks:
        for f in os.listdir("{}/crosswalk".format(region_name)):
            if f.endswith(".png"):
                full_path_img = os.path.abspath(os.path.join("{}/crosswalk".format(region_name), f))
                img = cv2.imread(full_path_img)
                try:
                    if img.shape[0] != img.shape[1]:
                        diff = abs(img.shape[1] - img.shape[0])
                        new_img = img[:-diff, :]
                        cv2.imwrite(full_path_img, new_img)
                except:
                    os.remove(full_path_img)
                    deleted_files += 1

    if download_no_crosswalks:
        for f in os.listdir("{}/no-crosswalk".format(region_name)):
            if f.endswith(".png"):
                full_path_img = os.path.abspath(os.path.join("{}/no-crosswalk".format(region_name), f))
                img = cv2.imread(full_path_img)
                try:
                    if img.shape[0] != img.shape[1]:
                        diff = abs(img.shape[1] - img.shape[0])
                        new_img = img[:-diff, :]
                        cv2.imwrite(full_path_img, new_img)
                except:
                    os.remove(full_path_img)
                    deleted_files += 1

    log_and_print('Deleted images: {}'.format(deleted_files))


def check_setup(region_name, download_crosswalk, download_no_crosswalk):
    directories = ['{}']

    if download_crosswalk:
        directories.append('{}/crosswalk')
    if download_no_crosswalk:
        directories.append('{}/no-crosswalk')

    for d in directories:
        _dir = d.format(region_name)
        if not os.path.exists(_dir):
            os.makedirs(_dir)
    # init logger
    log_fname = os.path.join(region_name, 'run.log')
    logging.basicConfig(filename=log_fname, filemode='w', format='[%(asctime)s] %(name)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
    logging.info('----------------------------------------')

    # disable log messages from the requests modules
    logging.getLogger("requests").setLevel(logging.CRITICAL)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)


def load_regions(regions_name):
    with open('regions.json') as hf:
        return json.load(hf)[regions_name]


def main(region_name, download_crosswalk_flag, download_no_crosswalk_flag, api_key=None):

    if api_key is None:
        exit('Go to console.developers.google.com and get an API_KEY: it is required!')
    global key
    key = api_key

    regions = load_regions(region_name)

    # get what is to be downloaded
    download_crosswalk = bool(int(download_crosswalk_flag))
    download_no_crosswalk = bool(int(download_no_crosswalk_flag))
    if (not download_crosswalk) and (not download_no_crosswalk):
        exit('Nothing to download. Bye!')

    # build download str
    download_str = "crosswalks" if download_crosswalk else "no-crosswalks"
    if download_crosswalk and download_no_crosswalk:
        download_str = "crosswalks and no-crosswalks"

    for region_data in regions:
        # init
        # =========================================================================================================
        start = time.time()
        region = region_data['region']
        region_name = region_data['name']
        check_setup(region_name, download_crosswalk, download_no_crosswalk)
        log_and_print('Downloading {} from {}: {}'.format(download_str, region_name, ','.join(map(str, region))))
        log_and_print('Using key: {}'.format(key))

        # 1. download crosswalk images
        # =========================================================================================================
        if download_crosswalk:
            # download the crosswalk locations using OpenStreetMap
            crosswalks = get_crosswalks(region_data['region'])
            save_to_json(crosswalks, '{}/crosswalks.json'.format(region_name))

            log_and_print('Downloading {} crosswalk images'.format(len(crosswalks)))
            download_images(crosswalks, 'crosswalk', region_name)
        else:
            log_and_print('Crosswalk images are not gonna be downloaded this time')

        # 2. download no-crosswalk images
        # =========================================================================================================
        if download_no_crosswalk:
            # we still need the crosswalk points
            if not download_crosswalk:
                if not os.path.isfile('{}/crosswalks.json'.format(region_name)):
                    crosswalks = get_crosswalks(region_data['region'])
                    save_to_json(crosswalks, '{}/crosswalks.json'.format(region_name))
                else:
                    with open('{}/crosswalks.json'.format(region_name)) as hf:
                        crosswalks = json.load(hf)

            if not os.path.isfile('{}/no_crosswalks.json'.format(region_name)):
                # download the polylines
                polylines, all_points, nb_duplicates, no_crosswalk_points = download_polylines_points(crosswalks, region)
                save_to_json(polylines, '{}/paths.json'.format(region_name))
                save_to_json(no_crosswalk_points, '{}/no_crosswalks.json'.format(region_name))
            else:
                with open('{}/no_crosswalks.json'.format(region_name)) as hf:
                    no_crosswalk_points = json.load(hf)
                with open('{}/paths.json'.format(region_name)) as hf:
                    polylines = json.load(hf)
                nb_duplicates = 'files were loaded'
                all_points = 'files were loaded'

            log_and_print('Downloading {} no-crosswalk images'.format(len(no_crosswalk_points)))
            download_images(no_crosswalk_points, 'no-crosswalk', region_name)

        # if any of the images were downloaded, crop the images
        # =========================================================================================================
        if download_crosswalk or download_no_crosswalk:
            log_and_print('Removing Google from the images')
            crop_images(region_name, download_crosswalk, download_no_crosswalk)

        # summary
        # =========================================================================================================
        log_and_print('-' * 50)
        log_and_print('SUMMARY - REGION {}'.format(region_name))
        if download_no_crosswalk:
            log_and_print('Number of paths: {}'.format(len(polylines)))
            log_and_print('Removed {} duplicate points from the paths'.format(nb_duplicates))
            log_and_print('Number of all points: {}'.format(len(all_points)))
            log_and_print('Number of no-crosswalk points: {}'.format(len(no_crosswalk_points)))
        if download_crosswalk:
            log_and_print('Number of crosswalk points: {}'.format(len(crosswalks)))
        log_and_print('-'*50)
        log_and_print('{} finished: {:.2f} seconds'.format(region_name, (time.time() - start)))


if __name__ == '__main__':

    if len(sys.argv) != 5:
        msg = '4 arguments required:\npython {} region_name {{download_crosswalk:0,1}} {{download_no_crosswalk:0,1}} API_KEY'
        exit(msg.format(os.path.basename(sys.argv[0])))

    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
