import streamlit as st

def main():
    st.markdown("# UTT App へようこそ！")
    st.markdown("都内BUZZスタジオの予約状況を一覧で確認できます。")

    st.markdown("## BUZZ予約表について")
    st.markdown("---")

    st.markdown("### 機能")
    st.write("都内BUZZスタジオの予約状況を一覧で取得します。")
    with st.expander("使い方"):
        st.write("1. 日付を入力して「予約表一覧を取得する」を押す")
        st.write("2. すると該当日の全スタジオの予約表をスクレイピングで取得した結果が表示される")
        st.image("image/buzz_01.png")
