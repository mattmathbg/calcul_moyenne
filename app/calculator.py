class Calculator:

    @staticmethod
    def _poids_valide(g):
        """Vérifie qu'un grade a un poids convertible en float > 0."""
        try:
            return float(g["poids"]) > 0
        except (TypeError, ValueError, KeyError):
            return False

    @staticmethod
    def _calculer_moyenne_ue(details):
        """Calcule la moyenne d'une UE (Pessimiste + Seconde Chance)."""
        grades = details.get("grades", [])
        sc = details.get("sc", None)

        num = sum(
            (float(g["note"]) if g["note"] is not None else 0.0) * float(g["poids"])
            for g in grades if Calculator._poids_valide(g)
        )
        den = sum(float(g["poids"]) for g in grades if Calculator._poids_valide(g))

        moy_init = num / den if den > 0 else 0.0

        moy_finale = moy_init
        if sc is not None:
            try:
                moy_finale = max(moy_init, (moy_init + float(sc)) / 2)
            except (TypeError, ValueError):
                pass

        return moy_finale

    @staticmethod
    def compute_stats(data):
        """Calcule S1, S2, Moyenne Annuelle, Moyenne Actuelle et Categories."""
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
            cat = details.get("categorie", "General")
            target = "S1" if sem in ["S1", 1] else "S2"

            grades = details.get("grades", [])

            valid_grades = []
            for g in grades:
                if not Calculator._poids_valide(g):
                    continue
                if g.get("note") is None:
                    continue
                try:
                    float(g["note"])
                    valid_grades.append(g)
                except (TypeError, ValueError):
                    pass

            moyenne_actuelle = None
            if valid_grades:
                moyenne_actuelle = (
                    sum(float(g["note"]) * float(g["poids"]) for g in valid_grades)
                    / sum(float(g["poids"]) for g in valid_grades)
                )
                stats["Actuelle"]["points"] += moyenne_actuelle * coef
                stats["Actuelle"]["coefs"] += coef

            if cat not in categories:
                categories[cat] = {"points": 0, "coefs": 0}
            categories[cat]["points"] += moyenne_pessimiste * coef
            categories[cat]["coefs"] += coef

            stats[target]["points"] += moyenne_pessimiste * coef
            stats[target]["coefs"] += coef
            stats[target]["ues"].append({
                "Nom": nom,
                "Moyenne": moyenne_pessimiste,
                "Moyenne Actuelle": moyenne_actuelle,
                "Coef": coef,
                "Semestre": target,
                "Categorie": cat
            })

        res = {}
        for key in ["S1", "S2"]:
            res[key] = stats[key]["points"] / stats[key]["coefs"] if stats[key]["coefs"] > 0 else 0.0

        res["Actuelle"] = (
            stats["Actuelle"]["points"] / stats["Actuelle"]["coefs"]
            if stats["Actuelle"]["coefs"] > 0 else 0.0
        )

        total_points = stats["S1"]["points"] + stats["S2"]["points"]
        total_coefs = stats["S1"]["coefs"] + stats["S2"]["coefs"]
        res["Annee"] = total_points / total_coefs if total_coefs > 0 else 0.0

        res["categories"] = {
            k: v["points"] / v["coefs"] if v["coefs"] > 0 else 0.0
            for k, v in categories.items()
        }

        res["details"] = stats["S1"]["ues"] + stats["S2"]["ues"]
        return res