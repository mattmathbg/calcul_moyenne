import streamlit as st
import glob
import importlib.util
import os
import json

class DataManager:
    @staticmethod
    def init_state():
        """Initialise la session si elle n'existe pas."""
        if "ue_data" not in st.session_state:
            st.session_state.ue_data = {}

    @staticmethod
    def normaliser_donnees(data_raw):
        """Nettoie et formatte les données brutes."""
        data_propre = {}
        for ue, details in data_raw.items():
            grades_clean = []
            raw_grades = details.get("grades", [])
            
            for g in raw_grades:
                note, poids = None, None
                if isinstance(g, (list, tuple)) and len(g) >= 2:
                    note, poids = g[0], g[1]
                elif isinstance(g, dict):
                    note, poids = g.get("note"), g.get("poids")
                
                if isinstance(note, str):
                    note = float(note) if note.replace('.', '', 1).isdigit() else None
                
                grades_clean.append({"note": note, "poids": poids})

            data_propre[ue] = {
                "coef": float(details.get("coef", 1.0)),
                "semestre": details.get("semestre", "S1"),
                "sc": details.get("seconde_chance", details.get("sc", None)),
                "grades": grades_clean
            }
        return data_propre

    @staticmethod
    def scanner_fichiers_locaux():
        """Trouve les fichiers ue_data_*.py locaux."""
        datasets = {}
        for filepath in glob.glob("ue_data_*.py"):
            try:
                spec = importlib.util.spec_from_file_location("module", filepath)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                vars_module = {k: v for k, v in vars(module).items() if k.startswith("ue_data_")}
                if vars_module: datasets[os.path.basename(filepath)] = vars_module
            except Exception: pass
        return datasets