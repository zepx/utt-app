import requests
from bs4 import BeautifulSoup
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import json

# Area, Studio Name, URL
# Organized by official BUZZ website area groupings (Tokyo central areas only)
buzz_tokyo_all = [
    # 渋谷
    ['渋谷', 'BUZZ渋谷', 'https://buzz-st.com/shibuya'],
    ['渋谷', 'BUZZ渋谷MARKCITY', 'https://buzz-st.com/shibuya4'],
    ['渋谷', 'BUZZ渋谷東口SQUARE', 'https://buzz-st.com/shibuya3'],
    ['渋谷', 'BUZZ渋谷宮下PARK', 'https://buzz-st.com/shibuya5'],
    ['渋谷', 'BUZZ渋谷TOWER', 'https://buzz-st.com/shibuya6'],

    # 六本木・赤坂・浜松町
    ['六本木・赤坂・浜松町', 'BUZZ赤坂', 'https://buzz-st.com/akasaka2'],
    ['六本木・赤坂・浜松町', 'BUZZ六本木', 'https://buzz-st.com/roppongi'],
    ['六本木・赤坂・浜松町', 'BUZZ Live 赤坂', 'https://buzz-st.com/live-akasaka'],
    ['六本木・赤坂・浜松町', 'BUZZ BAYSIDE(浜松町)', 'https://buzz-st.com/bayside'],

    # 新宿・代々木・大久保
    ['新宿・代々木・大久保', 'BUZZ代々木', 'https://buzz-st.com/yoyogi'],
    ['新宿・代々木・大久保', 'BUZZ新宿', 'https://buzz-st.com/shinjuku'],
    ['新宿・代々木・大久保', 'BUZZ新宿ハウス', 'https://buzz-st.com/shinjuku2'],
    ['新宿・代々木・大久保', 'BUZZ新宿4丁目', 'https://buzz-st.com/shinjuku3'],
    ['新宿・代々木・大久保', 'BUZZ新宿コンシェルジュ', 'https://buzz-st.com/shinjuku4'],
    ['新宿・代々木・大久保', 'BUZZ東新宿', 'https://buzz-st.com/shinjuku5'],
    ['新宿・代々木・大久保', 'BUZZ新宿駅前', 'https://buzz-st.com/shinjuku6'],
    ['新宿・代々木・大久保', 'BUZZ新宿西口', 'https://buzz-st.com/shinjuku7'],

    # 池袋・高田馬場
    ['池袋・高田馬場', 'BUZZ池袋サンシャイン', 'https://buzz-st.com/ikebukuro7'],
    ['池袋・高田馬場', 'BUZZ池袋東口BASE', 'https://buzz-st.com/ikebukuro5'],
    ['池袋・高田馬場', 'BUZZ池袋本店', 'https://buzz-st.com/ikebukuro4'],
    ['池袋・高田馬場', 'BUZZ池袋西口タワー', 'https://buzz-st.com/ikebukuro3'],
    ['池袋・高田馬場', 'BUZZ池袋西口PARK', 'https://buzz-st.com/ikebukuro6'],
    ['池袋・高田馬場', 'BUZZ南池袋', 'https://buzz-st.com/ikebukuro8'],
    ['池袋・高田馬場', 'BUZZ高田馬場', 'https://buzz-st.com/takadanobaba'],
    ['池袋・高田馬場', 'BUZZ高田馬場2丁目', 'https://buzz-st.com/takadanobaba2'],

    # 秋葉原・神田
    ['秋葉原・神田', 'BUZZ神田', 'https://buzz-st.com/kanda'],
    ['秋葉原・神田', 'BUZZ秋葉原', 'https://buzz-st.com/akihabara'],

    # 上野・日暮里・巣鴨
    ['上野・日暮里・巣鴨', 'BUZZ上野', 'https://buzz-st.com/ueno2'],
    ['上野・日暮里・巣鴨', 'BUZZ日暮里', 'https://buzz-st.com/nippori'],
    ['上野・日暮里・巣鴨', 'BUZZ西日暮里', 'https://buzz-st.com/nishinippori'],
    ['上野・日暮里・巣鴨', 'BUZZ巣鴨', 'https://buzz-st.com/sugamo'],
    ['上野・日暮里・巣鴨', 'BUZZ竹ノ塚', 'https://buzz-st.com/takenotsuka'],
]


# Time slots of the reservation table (30-minute increments, 06:00-23:30)
TIME_SLOTS = ['06:00', '06:30', '07:00', '07:30', '08:00', '08:30', '09:00', '09:30',
              '10:00', '10:30', '11:00', '11:30', '12:00', '12:30', '13:00', '13:30',
              '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00', '17:30',
              '18:00', '18:30', '19:00', '19:30', '20:00', '20:30', '21:00', '21:30',
              '22:00', '22:30', '23:00', '23:30']


def normalize_room_name(name):
    """Normalize room names so reservation table columns match studio_item titles
    (site markup pads studio_title text with whitespace/newlines)."""
    return ''.join(str(name).split())


def _extract_js_variable(source, var_name):
    """Extract the object/array literal assigned to a JS variable."""
    match = re.search(r'\b' + re.escape(var_name) + r'\s*=\s*([{\[])', source)
    if not match:
        return None
    open_ch = match.group(1)
    close_ch = '}' if open_ch == '{' else ']'
    depth = 0
    for i in range(match.end() - 1, len(source)):
        char = source[i]
        if char == open_ch:
            depth += 1
        elif char == close_ch:
            depth -= 1
            if depth == 0:
                return source[match.end() - 1:i + 1]
    return None


def _loads_js_literal(raw):
    """Parse a JS object literal (unquoted keys, trailing commas) as JSON."""
    raw = re.sub(r'([{,])\s*([A-Za-z_$][\w$]*|\d+)\s*:', r'\1"\2":', raw)
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    return json.loads(raw)


def parse_studio_slots_data(soup, selected_date):
    """
    Parse reservation data from StudioSlotsData/StudioArray JS variables
    (current buzz-st.com format: the reservation table body is generated
    client-side from these embedded variables).
    Returns dict of {room_name: {time: status}} or None.
    """
    try:
        source = '\n'.join(script.get_text() for script in soup.find_all('script'))

        slots_raw = _extract_js_variable(source, 'StudioSlotsData')
        studios_raw = _extract_js_variable(source, 'StudioArray')
        if not slots_raw or not studios_raw:
            return None

        slots_data = _loads_js_literal(slots_raw)
        studios = json.loads(studios_raw)
        date_str = selected_date.strftime('%Y-%m-%d')

        reservation_dict = {}
        for studio in studios:
            room_name = normalize_room_name(studio.get('name', ''))
            if not room_name:
                continue
            # Slot status: 0 = available, 1 = reserved (see reservation-calendar.js).
            # Slots missing from the data are not bookable.
            day_info = slots_data.get(str(studio.get('id')), {}).get('info', {}).get(date_str, {})
            reservation_dict[room_name] = {
                time: "◯" if day_info.get(time) == 0 else "×"
                for time in TIME_SLOTS
            }

        return reservation_dict or None

    except Exception:
        return None


def parse_js_reservation_data(soup, selected_date, selected_time):
    """
    Parse legacy ScheduleArrayInfoJson reservation data
    Returns dict of {room_name: {time: status}}
    """
    try:
        # Extract JSON data from JavaScript
        scripts = soup.find_all('script')
        schedule_data = None

        for script in scripts:
            if script.string and 'ScheduleArrayInfoJson' in script.string:
                # Extract the JSON data
                match = re.search(r'ScheduleArrayInfoJson\s*=\s*({[^;]+});', script.string)
                if match:
                    schedule_data = json.loads(match.group(1))
                    break

        if not schedule_data:
            return None

        # Convert selected_date to string format YYYY-MM-DD
        date_str = selected_date.strftime('%Y-%m-%d')

        # Parse the schedule data
        # Structure: schedule_data[studio_id][date][time] where 0 = available, booking_id = occupied
        reservation_dict = {}

        # Get room names from studio_item divs
        room_elements = soup.find_all(class_='studio_item')
        if not room_elements:
            return None

        for room_elem in room_elements:
            room_name = room_elem.find(class_='studio_title')
            if room_name:
                room_name = normalize_room_name(room_name.text)

                # Create time slots dictionary
                time_status = {}

                # Time list starts at 06:00 with 30-min intervals
                time_list = TIME_SLOTS

                # Get studio ID from the first key in schedule_data
                studio_id = list(schedule_data.keys())[0]
                day_schedule = schedule_data.get(studio_id, {}).get(date_str, {})

                for time in time_list:
                    # Check if time slot is available (0) or occupied (booking ID string)
                    status_value = day_schedule.get(time, 0)
                    time_status[time] = "◯" if status_value == 0 else "×"

                reservation_dict[room_name] = time_status

        return reservation_dict

    except Exception as e:
        return None

# 表を検索して各行を処理し、条件に応じてマークをつける
def get_reservation_state(table):
    marked_table = []
    rows = table.find_all('tr')
    for row in rows:
        marked_row = []
        cells = row.find_all('td')
        for cell in cells:
            button = cell.find('button')
            if button:
                button_class = button.get('class')
                # reserve_modal_trigger: ◯
                # studio_reserve_time_table_close: ×
                if 'studio_reserve_time_table_close' in button_class:
                    marked_row.append("×")
                elif 'reserve_modal_trigger' in button_class:
                    marked_row.append("◯")
            else:
                marked_row.append(cell.text.strip())
        marked_table.append(marked_row)
    return marked_table

def filter_rooms_by_area(spec_table, area_filter):
    if area_filter == "すべて":
        return spec_table

    min_area = int(area_filter.replace("㎡以上", ""))
    filtered_columns = []

    for room_name in spec_table.columns:
        area_text = spec_table.loc['広さ', room_name]
        try:
            area_value = float(area_text.replace('㎡', ''))
            if area_value >= min_area:
                filtered_columns.append(room_name)
        except:
            continue

    return spec_table[filtered_columns] if filtered_columns else spec_table.iloc[:, :0]

def main():
    st.title("BUZZ予約表一覧")

    st.write("東京のBUZZスタジオの予約表一覧です。日付を入力するとのその日の空き状況が確認できます。5人ほどなら15～20㎡、10人なら25～30㎡、それ以上なら40㎡以上が広さの目安となります。")

    # Get unique areas for filter
    areas = sorted(list(set([studio[0] for studio in buzz_tokyo_all])))
    areas.insert(0, "すべて")

    row1_col1, row1_col2 = st.columns([2,2])
    with row1_col1:
        selected_date = st.date_input("日付")
    with row1_col2:
        selected_area = st.selectbox("エリアでフィルター", areas, index=0)

    time_list = ['06:00', '06:30', '07:00', '07:30', '08:00', '08:30', '09:00', '09:30', '10:00', '10:30', '11:00', '11:30', '12:00', '12:30', '13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00', '17:30', '18:00', '18:30', '19:00', '19:30', '20:00', '20:30', '21:00', '21:30', '22:00', '22:30', '23:00', '23:30']

    col1, col2, col3 = st.columns([1,1,1])

    # Initialize session state for time tracking
    if 'start_time_value' not in st.session_state:
        # Calculate default start time (now + 1 hour, rounded to nearest 30 min)
        # Always use Asia/Tokyo timezone
        now = datetime.now(ZoneInfo("Asia/Tokyo"))
        start_dt = now + timedelta(hours=1)
        # Round to nearest 30 minutes
        minutes = 30 * round(start_dt.minute / 30)
        if minutes == 60:
            start_dt = (start_dt + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        else:
            start_dt = start_dt.replace(minute=minutes, second=0, microsecond=0)

        # Ensure time is within bounds (06:00 - 23:30)
        if start_dt.hour < 6:
            start_dt = start_dt.replace(hour=10, minute=0)
        elif start_dt.hour >= 23 and start_dt.minute > 30:
            start_dt = start_dt.replace(hour=14, minute=0)

        st.session_state.start_time_value = start_dt.time()
        end_dt = start_dt + timedelta(hours=1)
        st.session_state.end_time_value = end_dt.time()

    with col1:
        start_time_input = st.time_input("開始時刻", value=st.session_state.start_time_value, step=1800, key="start_time_input")

    # When start time changes, automatically update end time to be 1 hour later
    if start_time_input != st.session_state.start_time_value:
        st.session_state.start_time_value = start_time_input
        # Calculate end time (1 hour later)
        start_dt_temp = datetime.combine(datetime.today(), start_time_input)
        end_dt_temp = start_dt_temp + timedelta(hours=1)
        st.session_state.end_time_value = end_dt_temp.time()

    with col2:
        end_time_input = st.time_input("終了時刻", value=st.session_state.end_time_value, step=1800, key="end_time_input")

    # Update end time if user manually changed it
    if end_time_input != st.session_state.end_time_value:
        st.session_state.end_time_value = end_time_input

    # Convert time objects to string format for compatibility
    start_time = start_time_input.strftime('%H:%M')
    end_time = end_time_input.strftime('%H:%M')

    with col3:
        area_size_filter = st.selectbox("広さでフィルター", ["すべて", "15㎡以上", "20㎡以上", "25㎡以上", "30㎡以上", "40㎡以上"], index=0)

    # Calculate and display duration
    start_idx = time_list.index(start_time)
    end_idx = time_list.index(end_time)
    duration_slots = end_idx - start_idx
    duration_hours = duration_slots * 0.5

    # Display selected time range prominently
    st.info(f"🕐 選択時間: **{start_time} - {end_time}** ({duration_hours:.1f}時間)")

    selected_time = time_list[start_idx:end_idx]

    # Filter studios by selected area
    if selected_area == "すべて":
        filtered_studios = [[studio[1], studio[2]] for studio in buzz_tokyo_all]
    else:
        filtered_studios = [[studio[1], studio[2]] for studio in buzz_tokyo_all if studio[0] == selected_area]

    if st.button("予約表一覧を取得する"):
        for studio_name, studio_url in filtered_studios:
            try:
                table_url = f'{studio_url}/{selected_date}#time_table'
                response = requests.get(table_url)
                soup = BeautifulSoup(response.text, "html.parser")

                # 予約表の一覧
                table = soup.find('table', class_="studio_all_reserve_time_table")

                # スタジオ名/アクセスの表示
                info_catch = soup.find(class_='top_info_catch')
                info_text = info_catch.text if info_catch else ""
                st.markdown(f"[{studio_name}]({table_url}): {info_text}")

                # buzz-st.com page formats:
                # 1. Server-rendered HTML table with actual rows (legacy)
                # 2. StudioSlotsData/StudioArray JS variables (current format:
                #    the table body is generated client-side, so the HTML
                #    table shell exists but is empty)
                # 3. ScheduleArrayInfoJson JS variable (legacy)
                if table is not None and table.find('td'):
                    # Standard table-based parsing
                    table_columns = ['Time'] + [normalize_room_name(div.text) for div in table.find_all('div', class_="studio_reserve_time_table_studio_name")]
                    reservation_state = get_reservation_state(table)
                    reservation_table = pd.DataFrame(reservation_state, columns=table_columns).set_index('Time')
                else:
                    # JavaScript-based parsing
                    js_data = parse_studio_slots_data(soup, selected_date)
                    if js_data is None:
                        js_data = parse_js_reservation_data(soup, selected_date, selected_time)
                    if js_data is None:
                        st.warning(f"⚠️ {studio_name}: 予約情報を取得できませんでした")
                        continue

                    # Convert JavaScript data to DataFrame (transpose to match standard format)
                    # Standard format: rows=times, columns=rooms
                    reservation_table = pd.DataFrame(js_data)
                    reservation_table.index.name = 'Time'

                # 部屋のスペック
                room_names = []
                all_specs = []
                for room in soup.find_all(class_='studio_item'):
                    room_name = normalize_room_name(room.find(class_='studio_title').text)
                    spec = room.find(class_='studio_spec').find('span').text.split()[1]
                    room_names.append(room_name)
                    all_specs.append(spec)
                spec_table = pd.DataFrame(all_specs, index=room_names, columns=['広さ']).T

                # 広さでフィルター
                filtered_spec_table = filter_rooms_by_area(spec_table, area_size_filter)

                if not filtered_spec_table.empty:
                    # フィルターされた部屋のみの予約表を表示
                    filtered_reservation_table = reservation_table[reservation_table.columns.intersection(filtered_spec_table.columns)]

                    # 指定した時間帯すべてが空いている部屋のみを表示
                    available_rooms = []
                    for room in filtered_reservation_table.columns:
                        if all(filtered_reservation_table.loc[time, room] == "◯" for time in selected_time):
                            available_rooms.append(room)

                    if available_rooms:
                        available_table = filtered_reservation_table[available_rooms]
                        st.write(available_table.loc[selected_time])
                        st.write(filtered_spec_table[available_rooms])
                else:
                    st.write("広さの条件に合う部屋がありません。")

            except Exception as e:
                # Skip studios that have errors (e.g., different page structure)
                st.warning(f"⚠️ {studio_name}: 予約情報を取得できませんでした ({type(e).__name__}: {e})")
                continue

if __name__ == "__main__":
    main()