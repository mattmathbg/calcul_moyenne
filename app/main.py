import streamlit as st
from utils import inject_css
from ui import ui_sidebar, ui_dashboard, ui_input, ui_optimist

# 1. Config & Utils
st.set_page_config(page_title="Calculateur Master", layout="wide", page_icon="🎓")
inject_css()

# 2. Interface
def main():
    ui_sidebar()
    
    st.title("🎓 Calculateur de Moyenne & Compensation")
    
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📝 Saisie & UEs", "✨ Moyenne Sans 0"])
    
    with tab1:
        ui_dashboard()
    with tab2:
        ui_input()
    with tab3:
        ui_optimist()

if __name__ == "__main__":
    main()