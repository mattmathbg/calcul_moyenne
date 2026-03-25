class Calculator:
    @staticmethod
    def _calculer_moyenne_ue(details):
        """Calcule la moyenne d'une UE (Pessimiste + Seconde Chance)."""
        grades = details.get("grades", [])
        sc = details.get("sc", None)
        
        # Pessimiste : note manquante = 0
        # On force la conversion en float() pour éviter les TypeError
        num = sum((float(g["note"]) if g["note"] is not None else 0.0) * float(g["poids"]) 
                  for g in grades if g.get("poids"))
        den = sum(float(g["poids"]) for g in grades if g.get("poids"))
        
        moy_init = num / den if den > 0 else 0.0
        
        # Application Seconde Chance (Max entre moyenne et moyenne avec rattrapage)
        moy_finale = moy_init
        if sc is not None:
            moy_finale = max(moy_init, (moy_init + sc) / 2)
            
        return moy_finale

    @staticmethod
    def compute_stats(data):
        """Calcule S1, S2, Moyenne Annuelle, Moyenne Actuelle et Catégories."""
        stats = {
            "S1": {"points": 0, "coefs": 0, "ues": []},
            "S2": {"points": 0, "coefs": 0, "ues": []},
            "Actuelle": {"points": 0, "coefs": 0}
        }
        
        categories = {}
        
        for nom, details in data.items():
            moyenne_pessimiste = Calculator._calculer_moyenne_ue(details)
            coef = details.get("coef", 1.0)
            sem = details.get("semestre", "S1")
            cat = details.get("categorie", "Général")
            target = "S1" if sem in ["S1", 1] else "S2"
            
            # --- Calcul de la Moyenne Actuelle ---
            grades = details.get("grades", [])
            valid_grades = [g for g in grades if g.get("note") is not None and g.get("poids")]
            moyenne_actuelle = None
            if valid_grades:
                moyenne_actuelle = sum(g["note"] * g["poids"] for g in valid_grades) / sum(g["poids"] for g in valid_grades)
                stats["Actuelle"]["points"] += moyenne_actuelle * coef
                stats["Actuelle"]["coefs"] += coef

            # --- Statistiques par Catégorie ---
            if cat not in categories:
                categories[cat] = {"points": 0, "coefs": 0}
            categories[cat]["points"] += moyenne_pessimiste * coef
            categories[cat]["coefs"] += coef
            
            # Statistiques classiques par semestre
            stats[target]["points"] += moyenne_pessimiste * coef
            stats[target]["coefs"] += coef
            stats[target]["ues"].append({
                "Nom": nom, 
                "Moyenne": moyenne_pessimiste, 
                "Moyenne Actuelle": moyenne_actuelle,
                "Coef": coef,
                "Semestre": target,
                "Catégorie": cat
            })
        
        # Calculs finaux
        res = {}
        for key in ["S1", "S2"]:
            res[key] = stats[key]["points"] / stats[key]["coefs"] if stats[key]["coefs"] > 0 else 0.0
            
        # Moyenne Actuelle globale
        res["Actuelle"] = stats["Actuelle"]["points"] / stats["Actuelle"]["coefs"] if stats["Actuelle"]["coefs"] > 0 else 0.0
            
        # Moyenne Annuelle (Compensation)
        total_points = stats["S1"]["points"] + stats["S2"]["points"]
        total_coefs = stats["S1"]["coefs"] + stats["S2"]["coefs"]
        res["Année"] = total_points / total_coefs if total_coefs > 0 else 0.0
        
        # Moyennes par catégorie
        res["categories"] = {k: v["points"]/v["coefs"] if v["coefs"]>0 else 0.0 for k, v in categories.items()}
        
        res["details"] = stats["S1"]["ues"] + stats["S2"]["ues"]
        return res