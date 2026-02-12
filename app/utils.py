import streamlit as st
import sys
import subprocess

def inject_css():
    """Injecte le CSS personnalisé."""
    st.markdown("""
        <style>
        .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
        .stProgress > div > div > div > div { background-image: linear-gradient(to right, #ff4b4b, #ffa425, #2ecc71); }
        .success-box { padding: 10px; border-radius: 5px; background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .warning-box { padding: 10px; border-radius: 5px; background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
        </style>
    """, unsafe_allow_html=True)