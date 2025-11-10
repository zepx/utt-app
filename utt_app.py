import streamlit as st
from apps import buzz_reservation

def main():
    st.set_page_config(
        page_title="BUZZ予約表 - UTT App",
        page_icon="🎵",
        layout="wide",
        menu_items={}
    )

    with st.sidebar:
        st.markdown("""
            # UTT App
            都内BUZZスタジオの予約状況を一覧で確認
        """)

    buzz_reservation.main()

if __name__ == "__main__":
    main()