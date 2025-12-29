import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import io
import glob
import importlib.util
import os
import joblib

# ---------- CONFIGURATION PAGE ----------
st.set_page_config(
    page_title="Calculateur de Moyenne 🎓",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- CSS PERSONNALISÉ ----------
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #ff4b4b, #ffa425, #2ecc71);
    }
    </style>
""", unsafe_allow_html=True)

# ---------- GESTION DE L'ÉTAT (SESSION) ----------
if "ue_data" not in st.session_state:
    st.session_state.ue_data = {}

# ---------- FONCTIONS UTILITAIRES ----------

def normaliser_donnees(data_raw):
    """
    Convertit les données brutes (format V1 avec tuples) vers le format V2 (avec dicts)
    et assure que toutes les notes non remplies sont None.
    """
    data_propre = {}
    for ue, details in data_raw.items():
        # Copie de sécurité
        nouvelle_ue = {
            "coef": details.get("coef", 1.0),
            "sc": details.get("seconde_chance", details.get("sc", None)),
            "grades": []
        }
        
        # Conversion des notes
        raw_grades = details.get("grades", [])
        for g in raw_grades:
            note = None
            poids = None
            
            if isinstance(g, (list, tuple)) and len(g) >= 2:
                # V1: Tuple (note, poids)
                note = g[0]
                poids = g[1]
            elif isinstance(g, dict):
                # V2: Dict {'note': x, 'poids': y}
                note = g.get("note")
                poids = g.get("poids")
                
            # Assure que la note est None si elle n'est pas un nombre
            if note == '': note = None 
            if isinstance(note, str) and not note.replace('.', '', 1).isdigit():
                note = None
            
            nouvelle_ue["grades"].append({"note": note, "poids": poids})
                
        data_propre[ue] = nouvelle_ue
    return data_propre

def scanner_fichiers_locaux():
    """Scanne le dossier pour trouver les fichiers ue_data_*.py"""
    datasets = {}
    fichiers = glob.glob("ue_data_*.py")
    
    for filepath in fichiers:
        nom_fichier = os.path.basename(filepath)
        try:
            spec = importlib.util.spec_from_file_location("module", filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Récupère toutes les variables commençant par ue_data_
            vars_module = {k: v for k, v in vars(module).items() if k.startswith("ue_data_")}
            if vars_module:
                datasets[nom_fichier] = vars_module
        except Exception as e:
            print(f"Erreur chargement {filepath}: {e}")
            
    return datasets

def reset_app():
    st.session_state.ue_data = {}
    st.toast("Application réinitialisée !", icon="🗑️")

def calcul_metriques(data):
    """
    Calcule toutes les stats pour le dashboard, y compris la moyenne pessimiste.
    Une UE est comptée "Validée" SEULEMENT si la moyenne PESSIMISTE >= 10.
    """
    resultats_detail = []
    total_points_actuel = 0.0
    total_coef_actuel = 0.0 # Coef des UEs avec au moins une note reçue
    total_points_pessimiste = 0.0
    total_coef_pessimiste = 0.0 # Coef de toutes les UEs définies
    ue_validees = 0
    ue_total = 0

    for nom, details in data.items():
        coef = details.get("coef", 1.0)
        grades = details.get("grades", [])
        sc = details.get("sc", None)

        # 1. Calcul de la Moyenne Actuelle (uniquement les notes reçues)
        num_actuel = sum(g["note"] * g["poids"] for g in grades if g.get("note") is not None and g.get("poids") is not None)
        den_actuel = sum(g["poids"] for g in grades if g.get("note") is not None and g.get("poids") is not None)
        
        moyenne_ue_actuelle = num_actuel / den_actuel if den_actuel > 0 else 0.0

        # 2. Calcul de la Moyenne Pessimiste (notes reçues + 0 pour les manquantes)
        num_pessimiste = 0.0
        den_pessimiste = sum(g["poids"] for g in grades if g.get("poids") is not None)
        
        for g in grades:
            note = g.get("note")
            poids = g.get("poids")
            if poids is not None and poids > 0:
                if note is not None:
                    # Grade reçu
                    num_pessimiste += note * poids
                # Si note est None, on assume 0/20, donc 0 * poids.
        
        moyenne_ue_pessimiste = num_pessimiste / den_pessimiste if den_pessimiste > 0 else 0.0
        
        # --- Application de la Seconde Chance (SC) ---
        moyenne_ue_actuelle_sc = moyenne_ue_actuelle
        moyenne_ue_pessimiste_sc = moyenne_ue_pessimiste
        
        if sc is not None:
            moyenne_ue_actuelle_sc = max(moyenne_ue_actuelle, (moyenne_ue_actuelle + sc) / 2)
            moyenne_ue_pessimiste_sc = max(moyenne_ue_pessimiste, (moyenne_ue_pessimiste + sc) / 2)

        # --- Détermination du statut de validation (Strict) ---
        est_validee_secure = moyenne_ue_pessimiste_sc >= 10
        if est_validee_secure:
            ue_validees += 1

        # --- Mise à Jour des Totaux Globaux ---

        # 1. Total Actuel (pour l'affichage de la moyenne Actuelle et le tableau de détails)
        if den_actuel > 0:
            total_points_actuel += moyenne_ue_actuelle_sc * coef
            total_coef_actuel += coef

            # Icône visuelle pour le tableau
            if est_validee_secure:
                icon_statut = "🔒 Validé"
            elif moyenne_ue_actuelle_sc >= 10:
                icon_statut = "⏳ En cours"
            else:
                icon_statut = "⚠️ Danger"

            ue_total += 1 # Compte les UEs avec au moins une note

            resultats_detail.append({
                "UE": nom,
                "Coef": coef,
                "Moyenne": round(moyenne_ue_actuelle_sc, 2), # Affiche la moyenne actuelle dans le tableau
                "Statut": icon_statut
            })
        elif den_pessimiste > 0:
            # Si aucune note reçue, mais des notes prévues, on compte l'UE
            ue_total += 1

        # 2. Total Pessimiste (pour l'affichage de la moyenne Pessimiste)
        if den_pessimiste > 0:
            total_points_pessimiste += moyenne_ue_pessimiste_sc * coef
            total_coef_pessimiste += coef
        
    # --- Moyennes Générales Finales ---
    moyenne_gen_actuelle = total_points_actuel / total_coef_actuel if total_coef_actuel > 0 else 0.0
    moyenne_gen_pessimiste = total_points_pessimiste / total_coef_pessimiste if total_coef_pessimiste > 0 else 0.0

    return resultats_detail, moyenne_gen_actuelle, moyenne_gen_pessimiste, ue_validees, ue_total, total_coef_pessimiste

# ---------- SIDEBAR (MENU) ----------
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # --- SECTION GIT / FICHIERS LOCAUX ---
    st.subheader("📂 Fichiers locaux (Git)")
    datasets_locaux = scanner_fichiers_locaux()
    
    if datasets_locaux:
        fichier_choisi = st.selectbox("1. Fichier :", list(datasets_locaux.keys()))
        if fichier_choisi:
            vars_dispo = datasets_locaux[fichier_choisi]
            dataset_choisi = st.selectbox("2. Dataset :", list(vars_dispo.keys()))
            
            if st.button("Charger ce dataset"):
                raw_data = vars_dispo[dataset_choisi]
                # Conversion des données pour qu'elles matchent le format V2
                st.session_state.ue_data = normaliser_donnees(raw_data)
                st.toast(f"Dataset '{dataset_choisi}' chargé !", icon="🚀")
                st.rerun()
    else:
        st.caption("Aucun fichier 'ue_data_*.py' trouvé dans le dossier.")

    st.divider()

    # --- SECTION JSON ---
    with st.expander("💾 Sauvegarde JSON"):
        st.download_button("Export JSON", json.dumps(st.session_state.ue_data, indent=4), "notes.json")
        f = st.file_uploader("Import JSON", type="json")
        if f: 
            st.session_state.ue_data = json.load(f)
            st.rerun()
        if st.button("Tout effacer", type="primary"): reset_app()

# ---------- INTERFACE PRINCIPALE ----------
st.title("Calculateur de Moyenne Étudiante 🎓")

# Création des onglets
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Tableau de Bord", "📝 Saisie & UEs", "🔮 Simulation", "📋 Détails Raw", "🏆 classement", "🚀 Insertion Pro"])
# === TAB 1: DASHBOARD ===
with tab1:
    details, moy_actuelle, moy_pessimiste, valides, total_ues, total_coef_pessimiste = calcul_metriques(st.session_state.ue_data)    
    if not st.session_state.ue_data:
        st.info("👈 Utilisez le menu à gauche pour charger un fichier 'ue_data_*.py' ou commencez manuellement.")
    else:
        # Affichage des deux moyennes et des métriques
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Moyenne Actuelle", f"{moy_actuelle:.2f}/20", 
                    delta=f"{moy_actuelle-10:.2f} vs val. (Notes reçues)", 
                    delta_color="normal" if moy_actuelle >= 10 else "inverse")
        col2.metric("Moyenne Pessimiste", f"{moy_pessimiste:.2f}/20", 
                    delta=f"{moy_pessimiste-10:.2f} vs val. (Notes manquantes à 0)", 
                    delta_color="normal" if moy_pessimiste >= 10 else "inverse")
        col3.metric("UE Validées", f"{valides}/{total_ues}", help="Une UE est validée si sa moyenne PESSIMISTE est ≥ 10")
        col4.metric("Coefficients Totaux", total_coef_pessimiste) # Utilise le coefficient total de toutes les UEs

        c1, c2 = st.columns([1, 2])
        with c1:
            # Jauge basée sur la moyenne actuelle
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = moy_actuelle, title = {'text': "Moyenne Actuelle"},
                gauge = {'axis': {'range': [0, 20]}, 
                         'bar': {'color': "#2b86d9"},
                         'steps': [{'range': [0, 10], 'color': "#ffe0e0"}, {'range': [10, 20], 'color': "#e0ffe0"}],
                         'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 10}}
            ))
            fig_gauge.update_layout(height=250, margin=dict(l=20,r=20,t=30,b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        with c2:
            if details:
                df_res = pd.DataFrame(details)
                df_res['Color'] = df_res['Moyenne'].apply(lambda x: '#2ecc71' if x >= 10 else '#e74c3c')
                fig_bar = px.bar(df_res, x="UE", y="Moyenne", text="Moyenne", title="Résultats par UE (Notes Reçues)")
                fig_bar.update_traces(marker_color=df_res['Color'], textposition='outside')
                fig_bar.add_hline(y=10, line_dash="dash", line_color="black")
                st.plotly_chart(fig_bar, use_container_width=True)

# === TAB 2: SAISIE ===
with tab2:
    c_add, c_edit = st.columns([1, 2])
    with c_add:
        st.subheader("➕ Ajouter une UE")
        new_ue_name = st.text_input("Nom UE")
        new_ue_coef = st.number_input("Coef", 1.0, 20.0, step=0.5)
        # Ajout de l'option de Seconde Chance
        new_ue_sc = st.number_input("Note Seconde Chance (Optionnel)", 0.0, 20.0, None, step=0.5)
        if st.button("Créer"):
            if new_ue_name:
                st.session_state.ue_data[new_ue_name] = {"coef": new_ue_coef, "grades": [], "sc": new_ue_sc}
                st.rerun()

    with c_edit:
        st.subheader("✏️ Modifier les notes")
        if st.session_state.ue_data:
            ue_select = st.selectbox("UE à modifier", list(st.session_state.ue_data.keys()))
            curr_data = st.session_state.ue_data[ue_select]
            
            # Modifier le coefficient et la SC de l'UE
            curr_data["coef"] = st.number_input(
                "Coefficient de l'UE", 
                min_value=1.0, 
                max_value=20.0, 
                value=float(curr_data.get("coef", 1.0)), 
                key=f"coef_{ue_select}"
            )
            curr_data["sc"] = st.number_input("Note Seconde Chance", 0.0, 20.0, curr_data.get("sc"), key=f"sc_{ue_select}", help="Laissez vide pour désactiver.")
            
            # DataFrame pour l'éditeur
            df_grades = pd.DataFrame(curr_data["grades"])
            if df_grades.empty: df_grades = pd.DataFrame(columns=["note", "poids"])

            edited_df = st.data_editor(
                df_grades, num_rows="dynamic",
                column_config={
                    "note": st.column_config.NumberColumn("Note (laissez vide si non reçue)", min_value=0.0, max_value=20.0, step=0.5),
                    "poids": st.column_config.NumberColumn("Poids", min_value=0.0, max_value=1.0, step=0.1, help="Doit être 1.0 au total par UE.")
                }, key=f"ed_{ue_select}"
            )

            if st.button("💾 Sauvegarder notes & paramètres UE"):
                # Nettoyage des données
                clean = [g for g in edited_df.to_dict('records') if g.get('poids') is not None and g.get('poids') > 0]
                
                # Assurer que les notes sont None si elles sont vides/non numériques
                for item in clean:
                    if not isinstance(item['note'], (int, float)):
                        item['note'] = None
                        
                st.session_state.ue_data[ue_select]["grades"] = clean
                st.toast("Sauvegardé !", icon="✅")
                st.rerun()

# === TAB 3: SIMULATION BASÉE SUR LA PERFORMANCE ===
with tab3:
    st.subheader("🔮 Simulation & Objectifs")
    st.markdown("""
    Ici, ne touchez pas à la moyenne finale directement. 
    **Estimez plutôt la note que vous pensez obtenir** sur les examens restants.
    """)

    if not st.session_state.ue_data:
        st.warning("Veuillez d'abord charger des données ou créer des UEs.")
    else:
        # --- 1. Préparation des données ---
        col_graph, col_sliders = st.columns([2, 1])
        
        with col_sliders:
            st.caption("🎯 **Vos objectifs par UE :**")
            
            simulated_results = []
            total_points_sim = 0
            total_coef_sim = 0
            
            for nom, details in st.session_state.ue_data.items():
                coef = details.get("coef", 1.0)
                grades = details.get("grades", [])
                sc = details.get("sc", None)
                
                # Calcul des poids
                poids_total = sum(g["poids"] for g in grades if g.get("poids") is not None)
                poids_rempli = sum(g["poids"] for g in grades if g.get("note") is not None and g.get("poids") is not None)
                poids_manquant = poids_total - poids_rempli
                
                # Points déjà acquis
                points_acquis = sum(g["note"] * g["poids"] for g in grades if g.get("note") is not None and g.get("poids") is not None)
                
                # --- CAS 1 : UE Terminée (Tout est noté) ---
                if poids_manquant <= 0.01:
                    # Calcul de la moyenne finale
                    moyenne_ue = points_acquis / poids_total if poids_total > 0 else 0
                    if sc: moyenne_ue = max(moyenne_ue, (moyenne_ue + sc)/2)
                    
                    # Affichage fixe (pas de slider)
                    st.success(f"🔒 **{nom}** : {moyenne_ue:.2f}/20 (Terminé)")
                    simulated_results.append({"UE": nom, "Note Finale": moyenne_ue, "Coef": coef, "Type": "Fixé"})
                    total_points_sim += moyenne_ue * coef
                    total_coef_sim += coef
                
                # --- CAS 2 : UE en cours (Calcul d'objectif) ---
                else:
                    # Calcul de la note nécessaire pour avoir 10/20 de moyenne UE
                    target_10 = (10.0 * poids_total - points_acquis) / poids_manquant
                    
                    # Affichage de l'aide à la décision
                    msg_target = ""
                    if target_10 <= 0:
                        msg_target = "✅ Validé (même avec 0)"
                        st.markdown(f"**{nom}** ({coef}) : {msg_target}")
                    elif target_10 > 20:
                        msg_target = f"💀 Impossible (Max: {(points_acquis + 20*poids_manquant)/poids_total:.2f})"
                        st.markdown(f"**{nom}** ({coef}) : {msg_target}")
                    else:
                        msg_target = f"🎯 Il faut **{target_10:.2f}** sur le reste"
                        st.markdown(f"**{nom}** ({coef}) : {msg_target}")

                    # Slider : "Quelle note pensez-vous avoir sur le reste ?"
                    note_sur_reste = st.slider(
                        f"Moyenne espérée sur les exams manquants ({nom})",
                        min_value=0.0, max_value=20.0, value=10.0, step=0.5,
                        key=f"sim_input_{nom}",
                        label_visibility="collapsed"
                    )
                    
                    # Calcul de la moyenne finale SIMULÉE
                    moyenne_simulee = (points_acquis + (note_sur_reste * poids_manquant)) / poids_total
                    if sc: moyenne_simulee = max(moyenne_simulee, (moyenne_simulee + sc)/2)
                    
                    simulated_results.append({"UE": nom, "Note Finale": moyenne_simulee, "Coef": coef, "Type": "Simulé"})
                    total_points_sim += moyenne_simulee * coef
                    total_coef_sim += coef
                    
                    st.divider()

        # --- 3. Graphique & Moyenne Globale ---
        moyenne_generale_sim = total_points_sim / total_coef_sim if total_coef_sim > 0 else 0.0
        
        with col_graph:
            # Grosse métrique centrale
            st.metric(
                "Moyenne Générale Projetée", 
                f"{moyenne_generale_sim:.2f}/20",
                delta="Si vous obtenez les notes choisies à droite"
            )
            
            if simulated_results:
                df_sim = pd.DataFrame(simulated_results)
                # Couleur : Vert si > 10, Orange si Simulé < 10, Rouge si Fixé < 10
                colors = []
                for _, row in df_sim.iterrows():
                    if row["Note Finale"] >= 10: colors.append("#2ecc71") # Vert
                    elif row["Type"] == "Simulé": colors.append("#f1c40f") # Jaune/Orange
                    else: colors.append("#e74c3c") # Rouge
                
                df_sim['Color'] = colors
                
                fig = px.bar(
                    df_sim, 
                    x="UE", 
                    y="Note Finale", 
                    text="Note Finale",
                    range_y=[0, 20],
                    title="Simulation des Moyennes Finales"
                )
                fig.update_traces(marker_color=df_sim['Color'], texttemplate='%{y:.2f}', textposition='outside')
                fig.add_hline(y=10, line_dash="dash", line_color="black", annotation_text="Validation")
                
                st.plotly_chart(fig, use_container_width=True)
# === TAB 4: CLASSEMENT ===
with tab4:
    st.subheader("🏅 Classement des UEs (Moyenne Pessimiste)")
    st.markdown("Ce classement est basé sur la **moyenne pessimiste** (les notes non reçues valent 0).")

    if not st.session_state.ue_data:
        st.warning("Aucune donnée disponible pour le classement.")
    else:
        classement_data = []
        
        for nom, details in st.session_state.ue_data.items():
            grades = details.get("grades", [])
            sc = details.get("sc", None)
            
            # --- Calcul Moyenne Pessimiste ---
            num_pessimiste = 0.0
            den_pessimiste = sum(g["poids"] for g in grades if g.get("poids") is not None)
            notes_recues_count = 0
            
            for g in grades:
                note = g.get("note")
                poids = g.get("poids")
                
                if poids is not None and poids > 0:
                    if note is not None:
                        # Note reçue
                        num_pessimiste += note * poids
                        notes_recues_count += 1
                    # Si note est None, on ajoute 0 au numérateur (pessimiste)
            
            moyenne_ue_pessimiste = num_pessimiste / den_pessimiste if den_pessimiste > 0 else 0.0
            
            # Application Seconde Chance (SC)
            moyenne_finale = moyenne_ue_pessimiste
            if sc is not None:
                moyenne_finale = max(moyenne_ue_pessimiste, (moyenne_ue_pessimiste + sc) / 2)
            
            classement_data.append({
                "UE": nom,
                "Moyenne Pessimiste": moyenne_finale,
                "Notes Reçues": f"{notes_recues_count} / {len(grades)}",
                "Coef": details.get("coef", 1.0)
            })
            
        # Création du DataFrame et Tri
        if classement_data:
            df_classement = pd.DataFrame(classement_data)
            # Tri décroissant par moyenne
            df_classement = df_classement.sort_values(by="Moyenne Pessimiste", ascending=False)
            
            # Reset de l'index pour avoir un classement 1, 2, 3...
            df_classement.reset_index(drop=True, inplace=True)
            df_classement.index += 1
            
            # Affichage avec configuration des colonnes (Barre de progression pour la moyenne)
            st.dataframe(
                df_classement,
                use_container_width=True,
                column_config={
                    "Moyenne Pessimiste": st.column_config.ProgressColumn(
                        "Moyenne Pessimiste",
                        format="%.2f",
                        min_value=0,
                        max_value=20,
                    ),
                    "Notes Reçues": st.column_config.TextColumn(
                        "Notes Reçues",
                        help="Nombre de notes saisies sur le nombre total attendu"
                    ),
                    "Coef": st.column_config.NumberColumn(
                        "Coef",
                        format="%.1f"
                    )
                }
            )
            
# === TAB 5: CLASSEMENT (FICHIER SÉLECTIONNÉ) ===
with tab5:
    st.subheader(f"🏆 Classement du fichier : {fichier_choisi if 'fichier_choisi' in locals() else 'Inconnu'}")

    if 'datasets_locaux' not in locals() or 'fichier_choisi' not in locals() or not fichier_choisi:
        st.warning("Veuillez sélectionner un fichier valide dans la barre latérale (gauche).")
    else:
        groupe_data = datasets_locaux[fichier_choisi]
        
        classement_general = []
        classement_par_matiere = {} 
        toutes_les_matieres = set()

        # 1. Analyse de chaque élève
        for nom_dataset, data_raw in groupe_data.items():
            nom_eleve = nom_dataset.replace("ue_data_", "").capitalize()
            data_eleve = normaliser_donnees(data_raw)
            
            # --- A. Moyenne Générale & Comptage des notes ---
            _, _, moy_gen_pessimiste, _, _, _ = calcul_metriques(data_eleve)
            
            # Calcul du nombre de notes reçues vs total attendu
            nb_recu = 0
            nb_total = 0
            for ue_vals in data_eleve.values():
                grades = ue_vals.get("grades", [])
                nb_total += len(grades)
                # On compte une note si elle n'est pas None
                nb_recu += sum(1 for g in grades if g.get("note") is not None)

            classement_general.append({
                "Élève": nom_eleve,
                "Moyenne Générale": moy_gen_pessimiste,
                "Notes Reçues": f"{nb_recu}/{nb_total}"  # <--- Nouvelle Colonne
            })
            
            # --- B. Extraction par Matière ---
            for nom_ue, details_ue in data_eleve.items():
                toutes_les_matieres.add(nom_ue)
                grades = details_ue.get("grades", [])
                sc = details_ue.get("sc", None)
                
                num = sum(g["note"] * g["poids"] for g in grades if g.get("note") is not None and g.get("poids") is not None)
                den = sum(g["poids"] for g in grades if g.get("poids") is not None)
                moy_ue = num / den if den > 0 else 0.0
                
                if sc is not None:
                    moy_ue = max(moy_ue, (moy_ue + sc) / 2)
                
                if nom_ue not in classement_par_matiere:
                    classement_par_matiere[nom_ue] = []
                
                classement_par_matiere[nom_ue].append({
                    "Élève": nom_eleve,
                    "Moyenne": moy_ue
                })

        # 2. Affichage Classement Général
        st.markdown("### 🌍 Classement Général (Moyenne Pessimiste)")
        if classement_general:
            df_gen = pd.DataFrame(classement_general).sort_values(by="Moyenne Générale", ascending=False)
            df_gen.reset_index(drop=True, inplace=True)
            df_gen.index += 1
            
            # Podium
            if len(df_gen) >= 3:
                c1, c2, c3 = st.columns(3)
                c1.metric("🥇 1er", df_gen.iloc[0]['Élève'], f"{df_gen.iloc[0]['Moyenne Générale']:.2f}")
                c2.metric("🥈 2ème", df_gen.iloc[1]['Élève'], f"{df_gen.iloc[1]['Moyenne Générale']:.2f}")
                c3.metric("🥉 3ème", df_gen.iloc[2]['Élève'], f"{df_gen.iloc[2]['Moyenne Générale']:.2f}")

            # Tableau avec la nouvelle colonne configurée
            st.dataframe(
                df_gen,
                use_container_width=True,
                column_config={
                    "Moyenne Générale": st.column_config.ProgressColumn(
                        "Moyenne Générale", format="%.2f", min_value=0, max_value=20
                    ),
                    "Notes Reçues": st.column_config.TextColumn(
                        "Notes Reçues",
                        help="Nombre de notes saisies / Nombre total de notes prévues"
                    )
                }
            )
        
        st.divider()

        # 3. Affichage Classement par Matière
        st.markdown("### 📚 Classement par Matière")
        if toutes_les_matieres:
            matiere_selectionnee = st.selectbox("Voir le classement pour :", sorted(list(toutes_les_matieres)))
            if matiere_selectionnee:
                data_matiere = classement_par_matiere.get(matiere_selectionnee, [])
                if data_matiere:
                    df_mat = pd.DataFrame(data_matiere).sort_values(by="Moyenne", ascending=False)
                    df_mat.reset_index(drop=True, inplace=True)
                    df_mat.index += 1
                    
                    st.dataframe(
                        df_mat,
                        use_container_width=True,
                        column_config={
                            "Moyenne": st.column_config.ProgressColumn(
                                f"Moyenne {matiere_selectionnee}", format="%.2f", min_value=0, max_value=20
                            )
                        }
                    )
                else:
                    st.info(f"Pas de données pour {matiere_selectionnee}.")
        else:
            st.info("Aucune matière trouvée.")
# === TAB 6: PRÉDICTION INSERTION PRO (MODÈLE ML) ===
with tab6:
    st.subheader("🚀 Prédicteur d'Insertion & Salaire")
    
    # Vérification des fichiers
    if not os.path.exists('modele_insertion_master.pkl') or not os.path.exists('model_metadata.json'):
        st.warning("⚠️ Modèle non détecté. Exécutez la cellule d'export dans votre Notebook Projet.ipynb.")
    else:
        # Chargement
        model = joblib.load('modele_insertion_master.pkl')
        with open('model_metadata.json', 'r') as f:
            meta = json.load(f)

        st.info("Ce modèle prédit votre futur professionnel basé sur les données historiques des Masters.")
        
        c1, c2 = st.columns(2)
        with c1:
            s_disc = st.selectbox("Discipline", sorted(meta['categories']['discipline']))
            s_acad = st.selectbox("Académie", sorted(meta['categories']['academie']))
            s_sit = st.selectbox("Échéance", meta['categories']['situation'])
        with c2:
            s_poids = st.slider("Poids de la discipline (%)", 0.0, 100.0, 20.0)
            s_boursiers = st.slider("Taux de boursiers (%)", 0.0, 100.0, 30.0)
            s_annee = st.number_input("Année de référence", 2020, 2025, 2022)

        if st.button("Lancer la prédiction 🔮", use_container_width=True):
            # Préparation des données (One-Hot Encoding dynamique)
            input_df = pd.DataFrame(0, index=[0], columns=meta['features'])
            
            # Variables numériques
            if 'poids_de_la_discipline' in input_df.columns: input_df['poids_de_la_discipline'] = s_poids
            if 'de_diplomes_boursiers' in input_df.columns: input_df['de_diplomes_boursiers'] = s_boursiers
            if 'annee' in input_df.columns: input_df['annee'] = s_annee
            
            # Variables catégorielles (Dummies)
            for col in input_df.columns:
                if col in [f"discipline_{s_disc}", f"academie_{s_acad}", f"situation_{s_sit}"]:
                    input_df[col] = 1
            
            # Calcul
            preds = model.predict(input_df)
            
            # Affichage
            st.divider()
            res1, res2 = st.columns(2)
            res1.metric("Taux d'insertion estimé", f"{preds[0][0]:.1f} %")
            res2.metric("Salaire Net Médian", f"{preds[0][1]:,.0f} €")
            st.balloons()