import streamlit as st

st.set_page_config(page_title="DESKER 월별마감", layout="wide")

pg = st.navigation([
    st.Page("pages/사업부.py", title="DESKER 사업부"),
    st.Page("pages/bxm.py", title="BXM(온라인외부몰)"),
])
pg.run()
