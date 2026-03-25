import math

class Calculator:
    @staticmethod
    def _safe_float(val, default=None):
        if val is None or val == "":
            return default
        try:
            f = float(val)
            if math.isnan(f):
                return default
            return f
        except (ValueError, TypeError):
            return default
    @staticmethod
    def _calculer_moyenne_ue(details):
        """Calcule la moyenne d'une UE (Pessimiste + Seconde Chance)."""
        grades = details.get("grades", [])
        sc = Calculator._safe_float(details.get("sc"))
        
        # Pessimiste : note manquante = 0
        num = 0.0
        den = 0.0
        for g in grades:
            n = Calculator._safe_float(g.get("note"), 0.0)
            p = Calculator._safe_float(g.get("poids"), 0.0)
            if p > 0:
                num += n * p
                den += p
        
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
            "Actuelle": {"points": 0, "coefs": 0},
            "Actuelle_sans_0": {"points": 0, "coefs": 0},
            "S1_sans_0": {"points": 0, "coefs": 0},
            "S2_sans_0": {"points": 0, "coefs": 0}
        }
        
        categories = {}
        
        for nom, details in data.items():
            moyenne_pessimiste = Calculator._calculer_moyenne_ue(details)
            coef = Calculator._safe_float(details.get("coef"), 1.0)
            sem = details.get("semestre", "S1")
            cat = details.get("categorie", "Général")
            target = "S1" if sem in ["S1", 1] else "S2"
            
            # --- Calcul de la Moyenne Actuelle ---
            grades = details.get("grades", [])
            valid_grades = []
            for g in grades:
                n = Calculator._safe_float(g.get("note"))
                p = Calculator._safe_float(g.get("poids"))
                if n is not None and p is not None and p > 0:
                    valid_grades.append((n, p))
                    
            moyenne_actuelle = None
            if valid_grades:
                moyenne_actuelle = sum(n * p for n, p in valid_grades) / sum(p for n, p in valid_grades)
                stats["Actuelle"]["points"] += moyenne_actuelle * coef
                stats["Actuelle"]["coefs"] += coef

            # --- Calcul de la Moyenne sans 0 ---
            valid_grades_sans_0 = [(n, p) for n, p in valid_grades if n > 0]
            moyenne_sans_0 = None
            if valid_grades_sans_0:
                moyenne_sans_0 = sum(n * p for n, p in valid_grades_sans_0) / sum(p for n, p in valid_grades_sans_0)
                stats["Actuelle_sans_0"]["points"] += moyenne_sans_0 * coef
                stats["Actuelle_sans_0"]["coefs"] += coef
                stats[target + "_sans_0"]["points"] += moyenne_sans_0 * coef
                stats[target + "_sans_0"]["coefs"] += coef

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
                "Moyenne Sans 0": moyenne_sans_0,
                "Coef": coef,
                "Semestre": target,
                "Catégorie": cat
            })
        
        # Calculs finaux
        res = {}
        for key in ["S1", "S2"]:
            res[key] = stats[key]["points"] / stats[key]["coefs"] if stats[key]["coefs"] > 0 else 0.0
            
        for key in ["S1_sans_0", "S2_sans_0"]:
            res[key] = stats[key]["points"] / stats[key]["coefs"] if stats[key]["coefs"] > 0 else 0.0
            
        # Moyenne Actuelle globale
        res["Actuelle"] = stats["Actuelle"]["points"] / stats["Actuelle"]["coefs"] if stats["Actuelle"]["coefs"] > 0 else 0.0
        res["Actuelle_sans_0"] = stats["Actuelle_sans_0"]["points"] / stats["Actuelle_sans_0"]["coefs"] if stats["Actuelle_sans_0"]["coefs"] > 0 else 0.0
            
        # Moyenne Annuelle (Compensation)
        total_points = stats["S1"]["points"] + stats["S2"]["points"]
        total_coefs = stats["S1"]["coefs"] + stats["S2"]["coefs"]
        res["Année"] = total_points / total_coefs if total_coefs > 0 else 0.0
        
        # Moyennes par catégorie
        res["categories"] = {k: v["points"]/v["coefs"] if v["coefs"]>0 else 0.0 for k, v in categories.items()}
        
        res["details"] = stats["S1"]["ues"] + stats["S2"]["ues"]
        return res