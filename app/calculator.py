class Calculator:
    @staticmethod
    def _calculer_moyenne_ue(details):
        """Calcule la moyenne d'une UE (Pessimiste + Seconde Chance)."""
        grades = details.get("grades", [])
        sc = details.get("sc", None)
        
        # Pessimiste : note manquante = 0
        num = sum((g["note"] if g["note"] is not None else 0) * g["poids"] for g in grades if g["poids"])
        den = sum(g["poids"] for g in grades if g["poids"])
        
        moy_init = num / den if den > 0 else 0.0
        
        # Application Seconde Chance (Max entre moyenne et moyenne avec rattrapage)
        moy_finale = moy_init
        if sc is not None:
            moy_finale = max(moy_init, (moy_init + sc) / 2)
            
        return moy_finale

    @staticmethod
    def compute_stats(data):
        """Calcule S1, S2 et Moyenne Annuelle avec compensation."""
        stats = {
            "S1": {"points": 0, "coefs": 0, "ues": []},
            "S2": {"points": 0, "coefs": 0, "ues": []}
        }
        
        for nom, details in data.items():
            moyenne = Calculator._calculer_moyenne_ue(details)
            coef = details.get("coef", 1.0)
            # Détection du semestre (par défaut S1)
            sem = details.get("semestre", "S1")
            target = "S1" if sem in ["S1", 1] else "S2"
            
            stats[target]["points"] += moyenne * coef
            stats[target]["coefs"] += coef
            stats[target]["ues"].append({
                "Nom": nom, 
                "Moyenne": moyenne, 
                "Coef": coef,
                "Semestre": target
            })
        
        # Calculs finaux
        res = {}
        for key in ["S1", "S2"]:
            res[key] = stats[key]["points"] / stats[key]["coefs"] if stats[key]["coefs"] > 0 else 0.0
            
        # Moyenne Annuelle (Compensation)
        total_points = stats["S1"]["points"] + stats["S2"]["points"]
        total_coefs = stats["S1"]["coefs"] + stats["S2"]["coefs"]
        res["Année"] = total_points / total_coefs if total_coefs > 0 else 0.0
        
        res["details"] = stats["S1"]["ues"] + stats["S2"]["ues"]
        return res