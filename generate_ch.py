from lxml import etree
import requests
from datetime import datetime, timedelta, time, timezone
import pytz
import unicodedata

tz = pytz.timezone('Europe/Berlin')


def remove_control_characters(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")


def get_days() -> list:
    now = datetime.now().replace(hour=datetime.now().hour, minute=0, second=0, microsecond=0)
    day_1 = datetime.combine(datetime.now(), time(0, 0)) + timedelta(1)
    day_2 = datetime.combine(datetime.now(), time(0, 0)) + timedelta(2)
    day_3 = datetime.combine(datetime.now(), time(0, 0)) + timedelta(3)
    day_4 = datetime.combine(datetime.now(), time(0, 0)) + timedelta(4)
    day_5 = datetime.combine(datetime.now(), time(0, 0)) + timedelta(5)
    day_6 = datetime.combine(datetime.now(), time(0, 0)) + timedelta(6)

    return [now, day_1, day_2, day_3, day_4, day_5, day_6]


def build_xmltv(channels: list, programmes: list) -> bytes:
    dt_format = '%Y%m%d%H%M%S %z'

    data = etree.Element("tv")
    data.set("generator-info-name", "Fellfresse")
    data.set("generator-info", "EPG/RakutenTV-CH")
    for ch in channels:
        channel = etree.SubElement(data, "channel")
        channel.set("id", str(ch.get("id")))
        name = etree.SubElement(channel, "display-name")
        name.set("lang", ch.get("language", "de")[:-1].lower() if ch.get("language") else "de")
        name.text = ch.get("name")
        if ch.get("icon") is not None:
            icon_src = etree.SubElement(channel, "icon")
            icon_src.set("src", ch.get("icon"))
            icon_src.text = ''
    for pr in programmes:
        programme = etree.SubElement(data, 'programme')
        start_time = datetime.fromtimestamp(pr.get('starts_at'), tz).strftime(dt_format).strip()
        end_time = datetime.fromtimestamp(pr.get('ends_at'), tz).strftime(dt_format).strip()

        programme.set("channel", str(pr.get('channel_id')))
        programme.set("start", start_time)
        programme.set("stop", end_time)

        title = etree.SubElement(programme, "title")
        title.set('lang', 'de')
        title.text = pr.get("title")

        if pr.get("subtitle") is not None:
            subtitle = etree.SubElement(programme, "sub-title")
            subtitle.set('lang', 'de')
            subtitle.text = remove_control_characters(pr.get("subtitle"))

        if pr.get('description') is not None:
            description = etree.SubElement(programme, "desc")
            description.set('lang', 'de')
            description.text = remove_control_characters(pr.get("description"))

        if pr.get('tags') is not None:
            if len(pr.get('tags')) > 0:
                category = etree.SubElement(programme, "category")
                category.set('lang', 'de')
                for tag in pr.get('tags'):
                    category.text = tag.get("name")

    return etree.tostring(data, pretty_print=True, encoding='utf-8')


days = get_days()

url = "https://gizmo.rakuten.tv/v3/live_channels"

base_params = {
    "classification_id": "319",
    "device_identifier": "web",
    "device_stream_audio_quality": "2.0",
    "device_stream_hdr_type": "NONE",
    "device_stream_video_quality": "FHD",
    "epg_duration_minutes": "360",
    "epg_ends_at": days[-1].strftime('%Y-%m-%dT%H:%M:%S.000Z'),
    "epg_ends_at_timestamp": int(days[-1].timestamp()),
    "epg_starts_at": days[0].strftime('%Y-%m-%dT%H:%M:%S.000Z'),
    "epg_starts_at_timestamp": int(days[0].timestamp()),
    "locale": "de",
    "market_code": "ch",
    "per_page": "25"
}

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://rakuten.tv",
    "Referer": "https://rakuten.tv/"
}

print("Grabbing data")

json = []
page = 1

while True:
    params = base_params.copy()
    params["page"] = str(page)
    
    res = requests.get(url, params=params, headers=headers)
    if res.status_code != 200:
        print(f"Server response ({res.status_code}): {res.text}")
        raise ConnectionError(f"HTTP{res.status_code}: could not get info from server!")

    page_data = res.json().get('data', [])
    if not page_data:
        break

    json.extend(page_data)
    print(f"Loading JSON {page} ({len(page_data)} channels)")
    page += 1

print(f"\nRetrieved {len(json)} channels:")

channels_data = []
programme_data = []

for channel in json:
    ch_name = channel['title']
    print(ch_name)
    ch_number = channel['channel_number']
    ch_id = channel['id']
    
    images = channel.get('images') or {}
    ch_icon = images.get('artwork_negative') or images.get('artwork')
    
    labels = channel.get('labels') or {}
    languages = labels.get('languages') or []
    ch_language = languages[0].get('id') if languages else "de"
    ch_tags = labels.get('tags')
    
    channels_data.append({
        "name": ch_name,
        "epg_number": ch_number,
        "id": ch_id,
        "icon": ch_icon,
        "language": ch_language,
        "tags": ch_tags
    })
    
    programmes_list = channel.get('live_programs', [])
    for item in programmes_list:
        title = item['title']
        subtitle = item.get('subtitle')
        description = item.get('description')
        start = datetime.strptime(item['starts_at'], '%Y-%m-%dT%H:%M:%S.000%z').timestamp()
        end = datetime.strptime(item['ends_at'], '%Y-%m-%dT%H:%M:%S.000%z').timestamp()

        programme_data.append({
            "title": title,
            "subtitle": subtitle,
            "description": description,
            "starts_at": start,
            "ends_at": end,
            "channel_id": ch_id,
            "language": ch_language,
            "tags": ch_tags,
        })

channel_xml = build_xmltv(channels_data, programme_data)

with open('Rakuten_CH_epg.xml', 'wb') as f:
    f.write(channel_xml)
