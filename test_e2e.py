"""E2E tests for utt-app against the live buzz-st.com site."""
import datetime

import pandas as pd
import pytest
import requests
from bs4 import BeautifulSoup

from apps.buzz_reservation import (
    buzz_tokyo_all,
    filter_rooms_by_area,
    get_reservation_state,
    parse_js_reservation_data,
)

TODAY = datetime.date.today()
TIME_LIST = ['%02d:%02d' % (h, m) for h in range(6, 24) for m in (0, 30)]
SELECTED_TIME = TIME_LIST[8:14]  # 10:00–13:00, safely inside every table


def scrape_studio(studio_url, date=TODAY):
    """Mirror of main()'s per-studio pipeline (both HTML and JS paths)."""
    response = requests.get(f'{studio_url}/{date}', timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # 予約表 — HTML table first, then the JS / ScheduleArrayInfoJson fallback
    table = soup.find('table', class_="studio_all_reserve_time_table")
    if table is not None:
        columns = ['Time'] + [d.text for d in table.find_all(
            'div', class_="studio_reserve_time_table_studio_name")]
        df = pd.DataFrame(get_reservation_state(table),
                          columns=columns).set_index('Time')
    else:
        js_data = parse_js_reservation_data(soup, date, SELECTED_TIME)
        assert js_data, 'no HTML table and no ScheduleArrayInfoJson data'
        df = pd.DataFrame(js_data)
        df.index.name = 'Time'

    assert not df.empty, 'empty reservation table'
    sliced = df.loc[SELECTED_TIME]
    marks = set(pd.unique(sliced.values.astype(object).ravel()))
    assert marks <= {'◯', '×'}, f'unexpected cell values: {marks}'

    # 部屋のスペック + 広さフィルター
    room_names, specs = [], []
    for room in soup.find_all(class_='studio_item'):
        room_names.append(room.find(class_='studio_title').text.replace(' ', ''))
        specs.append(room.find(class_='studio_spec').find('span').text.split()[1])
    assert room_names, 'no room specs found'
    spec_table = pd.DataFrame(specs, index=room_names, columns=['広さ']).T

    assert len(filter_rooms_by_area(spec_table, 'すべて').columns) == len(room_names)
    rooms_15 = len(filter_rooms_by_area(spec_table, '15㎡以上').columns)
    rooms_40 = len(filter_rooms_by_area(spec_table, '40㎡以上').columns)
    assert 0 <= rooms_40 <= rooms_15 <= len(room_names)
    return df, spec_table


@pytest.mark.parametrize('area,studio_name,studio_url', buzz_tokyo_all,
                         ids=[name for _, name, _ in buzz_tokyo_all])
def test_studio_scrape(area, studio_name, studio_url):
    scrape_studio(studio_url)


def test_streamlit_app_end_to_end():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file('utt_app.py', default_timeout=600)
    at.run()
    assert not at.exception, f'script crashed on load: {at.exception}'
    at.button[0].click().run()
    assert not at.exception, f'script crashed after button click: {at.exception}'
    # every studio must produce output (link header, or a warning on error)
    assert len(at.markdown) + len(at.warning) >= len(buzz_tokyo_all)
    # and at least some rooms should be available somewhere in Tokyo
    assert len(at.dataframe) > 0
