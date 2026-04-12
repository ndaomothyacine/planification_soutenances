import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import networkx as nx
from itertools import combinations
import numpy as np
from collections import defaultdict
import random
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import io
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side


# Jours en français (strftime("%A") retourne l'anglais sur Windows/Linux)
JOURS_FR = {0: "lundi", 1: "mardi", 2: "mercredi", 3: "jeudi",
            4: "vendredi", 5: "samedi", 6: "dimanche"}

def jour_fr(d):
    """Retourne la date au format 'lundi 23/06/2025' quelle que soit la plateforme."""
    return f"{JOURS_FR[d.weekday()]} {d.strftime('%d/%m/%Y')}"


st.set_page_config(page_title="Planification Soutenances", layout="wide")
st.title("Planification Optimisée des Soutenances de Stage")

# Configuration des étapes
etapes = [
    "etudiants", "salles", "duree_soutenance", "co_jury",
    "dates", "disponibilites", "disponibilites_selection", "generation"
]

etapes_labels = {
    "etudiants": "Étape 1 : Étudiants",
    "salles": "Étape 2 : Salles",
    "duree_soutenance": "Étape 3 : Durée",
    "co_jury": "Étape 4 : Co-jurys",
    "dates": "Étape 5 : Dates",
    "disponibilites": "Étape 6 : Créneaux",
    "disponibilites_selection": "Étape 7 : Disponibilités",
    "generation": "Étape 8 : Planning"
}


def afficher_navigation():
    st.sidebar.markdown("### 🧭 Navigation")
    etape_selectionnee = st.sidebar.selectbox(
        "Aller à une autre étape :",
        options=etapes,
        format_func=lambda x: etapes_labels.get(x, x),
        index=etapes.index(st.session_state.etape) if st.session_state.etape in etapes else 0
    )
    if etape_selectionnee != st.session_state.etape:
        st.session_state.etape = etape_selectionnee
        st.rerun()


# Initialisation des variables de session
if "etape" not in st.session_state:
    st.session_state.etape = "etudiants"
if "etudiants" not in st.session_state:
    st.session_state.etudiants = []
if "co_jurys" not in st.session_state:
    st.session_state.co_jurys = []
if "dates_soutenance" not in st.session_state:
    st.session_state.dates_soutenance = []
if "disponibilites" not in st.session_state:
    st.session_state.disponibilites = {}
if "planning_final" not in st.session_state:
    st.session_state.planning_final = []
if "nb_salles" not in st.session_state:
    st.session_state.nb_salles = 2
if "duree_soutenance" not in st.session_state:
    st.session_state.duree_soutenance = 50


@dataclass
class Individu:
    """Représente un individu (solution) dans l'algorithme génétique"""
    genes: List[int]  # Pour chaque étudiant, l'index du créneau assigné (-1 si non assigné)
    fitness: float = 0.0
    soutenances_planifiees: int = 0
    conflits: int = 0


class AlgorithmeGenetique:
    def __init__(self, planificateur, taille_population=80, nb_generations=800,
                 taux_mutation=0.12, taux_croisement=0.8):
        self.planificateur = planificateur
        self.taille_population = taille_population
        self.nb_generations = nb_generations
        self.taux_mutation = taux_mutation
        self.taux_croisement = taux_croisement

        # Pré-calculer les créneaux valides pour chaque étudiant
        self.creneaux = planificateur.generer_creneaux_uniques()
        self.creneaux_valides_par_etudiant = self._precalculer_creneaux_valides()
        self.nb_etudiants = len(planificateur.etudiants)

        # Statistiques
        self.historique_fitness = []
        self.meilleure_solution = None

    def _precalculer_creneaux_valides(self):
        """Pré-calcule les créneaux valides pour chaque étudiant"""
        creneaux_valides = {}

        for idx_etu, etudiant in enumerate(self.planificateur.etudiants):
            tuteur = etudiant["Tuteur"]
            creneaux_possibles = []

            for idx_creneau, creneau in enumerate(self.creneaux):
                if self.planificateur.est_disponible(tuteur, creneau['jour'], creneau['heure']):
                    co_jurys_disponibles = self.planificateur.trouver_co_jurys_disponibles(
                        tuteur, creneau['jour'], creneau['heure']
                    )
                    if co_jurys_disponibles:
                        creneaux_possibles.append(idx_creneau)

            creneaux_valides[idx_etu] = creneaux_possibles

        return creneaux_valides

    def generer_individu_intelligent(self) -> Individu:
        """Génère un individu en respectant les contraintes dès le départ"""
        genes = [-1] * self.nb_etudiants
        creneaux_occupes = set()
        jurys_par_moment = {}

        ordre_etudiants = list(range(self.nb_etudiants))
        random.shuffle(ordre_etudiants)

        for idx_etu in ordre_etudiants:
            creneaux_possibles = self.creneaux_valides_par_etudiant[idx_etu].copy()
            random.shuffle(creneaux_possibles)

            for idx_creneau in creneaux_possibles:
                creneau = self.creneaux[idx_creneau]

                if idx_creneau in creneaux_occupes:
                    continue

                tuteur = self.planificateur.etudiants[idx_etu]["Tuteur"]
                moment = creneau['moment']

                if moment not in jurys_par_moment:
                    jurys_par_moment[moment] = set()

                if tuteur in jurys_par_moment[moment]:
                    continue

                co_jurys_disponibles = self.planificateur.trouver_co_jurys_disponibles(
                    tuteur, creneau['jour'], creneau['heure']
                )

                co_jury_libre = None
                for co_jury in co_jurys_disponibles:
                    if co_jury not in jurys_par_moment[moment]:
                        co_jury_libre = co_jury
                        break

                if co_jury_libre:
                    genes[idx_etu] = idx_creneau
                    creneaux_occupes.add(idx_creneau)
                    jurys_par_moment[moment].add(tuteur)
                    jurys_par_moment[moment].add(co_jury_libre)
                    break

        return Individu(genes=genes)

    def calculer_fitness_amelioree(self, individu: Individu) -> Individu:
        """Fonction de fitness plus précise et équilibrée"""
        planning = self.decoder_individu(individu)

        nb_soutenances = len(planning)
        nb_total = len(self.planificateur.etudiants)
        taux_planification = nb_soutenances / nb_total if nb_total > 0 else 0

        conflits_salle, conflits_jury = self._analyser_conflits_detailles(planning)
        total_conflits = conflits_salle + conflits_jury

        equilibrage = self._calculer_equilibrage_charge(planning)
        bonus_alternance = self._calculer_bonus_alternance(planning)

        fitness = (
                taux_planification * 1000 +
                max(0, (nb_soutenances - 20)) * 50 +
                equilibrage * 20 +
                bonus_alternance * 10 -
                total_conflits * 500 -
                (nb_total - nb_soutenances) * 100
        )

        if total_conflits == 0 and nb_soutenances > 30:
            fitness += 2000

        individu.fitness = fitness
        individu.soutenances_planifiees = nb_soutenances
        individu.conflits = total_conflits

        return individu

    def _analyser_conflits_detailles(self, planning):
        """Analyse détaillée des conflits"""
        conflits_salle = 0
        conflits_jury = 0

        creneaux_salle = {}
        jurys_par_moment = {}

        for soutenance in planning:
            cle_salle = f"{soutenance['Jour']}_{soutenance['Créneau']}_{soutenance['Salle']}"
            moment = f"{soutenance['Jour']}_{soutenance['Créneau']}"

            if cle_salle in creneaux_salle:
                conflits_salle += 1
            creneaux_salle[cle_salle] = True

            if moment not in jurys_par_moment:
                jurys_par_moment[moment] = set()

            tuteur = soutenance['Tuteur']
            co_jury = soutenance['Co-jury']

            if tuteur in jurys_par_moment[moment]:
                conflits_jury += 1
            if co_jury in jurys_par_moment[moment]:
                conflits_jury += 1

            jurys_par_moment[moment].add(tuteur)
            jurys_par_moment[moment].add(co_jury)

        return conflits_salle, conflits_jury

    def _calculer_equilibrage_charge(self, planning):
        """Calcule un score d'équilibrage des charges"""
        if not planning:
            return 0

        charges = {}
        for soutenance in planning:
            tuteur = soutenance['Tuteur']
            co_jury = soutenance['Co-jury']
            charges[tuteur] = charges.get(tuteur, 0) + 1
            charges[co_jury] = charges.get(co_jury, 0) + 1

        if len(charges) <= 1:
            return 0

        valeurs_charges = list(charges.values())
        moyenne = sum(valeurs_charges) / len(valeurs_charges)
        variance = sum((x - moyenne) ** 2 for x in valeurs_charges) / len(valeurs_charges)

        return max(0, 10 - variance)

    def _calculer_bonus_alternance(self, planning):
        """Calcule un bonus pour l'alternance des créneaux des jurys"""
        bonus = 0
        jurys_par_periode = {'matin': set(), 'apres_midi': set()}

        for soutenance in planning:
            debut = soutenance['Début']
            periode = 'matin' if debut.hour < 14 else 'apres_midi'

            jurys_par_periode[periode].add(soutenance['Tuteur'])
            jurys_par_periode[periode].add(soutenance['Co-jury'])

        jurys_equilibres = jurys_par_periode['matin'] & jurys_par_periode['apres_midi']
        bonus += len(jurys_equilibres) * 2

        return bonus

    def croisement_intelligent(self, parent1: Individu, parent2: Individu) -> Tuple[Individu, Individu]:
        """Croisement qui préserve la validité des solutions"""
        enfant1_genes = [-1] * len(parent1.genes)
        enfant2_genes = [-1] * len(parent2.genes)

        point_croisement = random.randint(1, len(parent1.genes) - 1)

        for i in range(point_croisement):
            enfant1_genes[i] = parent1.genes[i]
            enfant2_genes[i] = parent2.genes[i]

        creneaux_utilises_e1 = set(g for g in enfant1_genes[:point_croisement] if g != -1)
        creneaux_utilises_e2 = set(g for g in enfant2_genes[:point_croisement] if g != -1)

        for i in range(point_croisement, len(parent1.genes)):
            if parent2.genes[i] != -1 and parent2.genes[i] not in creneaux_utilises_e1:
                enfant1_genes[i] = parent2.genes[i]
                creneaux_utilises_e1.add(parent2.genes[i])

            if parent1.genes[i] != -1 and parent1.genes[i] not in creneaux_utilises_e2:
                enfant2_genes[i] = parent1.genes[i]
                creneaux_utilises_e2.add(parent1.genes[i])

        return Individu(genes=enfant1_genes), Individu(genes=enfant2_genes)

    def mutation_adaptative(self, individu: Individu) -> Individu:
        """Mutation qui améliore les solutions existantes"""
        for i in range(len(individu.genes)):
            if random.random() < self.taux_mutation:
                if individu.genes[i] == -1:
                    creneaux_possibles = self.creneaux_valides_par_etudiant[i]
                    if creneaux_possibles:
                        creneaux_libres = [c for c in creneaux_possibles if c not in individu.genes]
                        if creneaux_libres:
                            individu.genes[i] = random.choice(creneaux_libres)
                else:
                    creneaux_possibles = self.creneaux_valides_par_etudiant[i]
                    if creneaux_possibles:
                        nouveau_creneau = random.choice(creneaux_possibles)
                        if nouveau_creneau not in individu.genes or nouveau_creneau == individu.genes[i]:
                            individu.genes[i] = nouveau_creneau

        return individu

    def evoluer(self) -> Tuple[List[Dict], Dict]:
        """Algorithme génétique principal amélioré"""
        population = []
        for _ in range(self.taille_population):
            individu = self.generer_individu_intelligent()
            population.append(self.calculer_fitness_amelioree(individu))

        self.meilleure_solution = max(population, key=lambda x: x.fitness)
        stagnation = 0

        for generation in range(self.nb_generations):
            nouvelle_population = []

            population_triee = sorted(population, key=lambda x: x.fitness, reverse=True)
            elite_size = max(5, self.taille_population // 8)
            nouvelle_population.extend(population_triee[:elite_size])

            while len(nouvelle_population) < self.taille_population:
                if random.random() < self.taux_croisement:
                    parent1 = self.selection_tournament(population, k=5)
                    parent2 = self.selection_tournament(population, k=5)

                    enfant1, enfant2 = self.croisement_intelligent(parent1, parent2)

                    enfant1 = self.mutation_adaptative(enfant1)
                    enfant2 = self.mutation_adaptative(enfant2)

                    nouvelle_population.extend([enfant1, enfant2])
                else:
                    nouvel_individu = self.generer_individu_intelligent()
                    nouvelle_population.append(nouvel_individu)

            nouvelle_population = nouvelle_population[:self.taille_population]
            population = [self.calculer_fitness_amelioree(ind) for ind in nouvelle_population]

            meilleur_actuel = max(population, key=lambda x: x.fitness)
            if meilleur_actuel.fitness > self.meilleure_solution.fitness:
                self.meilleure_solution = meilleur_actuel
                stagnation = 0
            else:
                stagnation += 1

            if stagnation > 50 and generation < self.nb_generations - 100:
                nb_nouveaux = self.taille_population // 3
                nouveaux = [self.generer_individu_intelligent() for _ in range(nb_nouveaux)]
                population = population[:-nb_nouveaux] + nouveaux
                stagnation = 0

            fitness_moyenne = sum(ind.fitness for ind in population) / len(population)
            self.historique_fitness.append({
                'generation': generation,
                'fitness_max': meilleur_actuel.fitness,
                'fitness_moyenne': fitness_moyenne,
                'soutenances_max': meilleur_actuel.soutenances_planifiees,
                'conflits_min': meilleur_actuel.conflits
            })

        planning_final = self.decoder_individu(self.meilleure_solution)

        statistiques = {
            'generations': self.nb_generations,
            'fitness_finale': self.meilleure_solution.fitness,
            'soutenances_planifiees': self.meilleure_solution.soutenances_planifiees,
            'conflits': self.meilleure_solution.conflits,
            'taux_reussite': self.meilleure_solution.soutenances_planifiees / len(self.planificateur.etudiants),
            'historique': self.historique_fitness
        }

        return planning_final, statistiques

    def selection_tournament(self, population: List[Individu], k=3) -> Individu:
        """Sélection par tournoi"""
        participants = random.sample(population, min(k, len(population)))
        return max(participants, key=lambda x: x.fitness)

    def decoder_individu(self, individu: Individu) -> List[Dict]:
        """Décode un individu en planning détaillé"""
        planning = []

        for idx_etu, idx_creneau in enumerate(individu.genes):
            if idx_creneau == -1:
                continue

            etudiant = self.planificateur.etudiants[idx_etu]
            creneau = self.creneaux[idx_creneau]
            tuteur = etudiant["Tuteur"]

            co_jurys_disponibles = self.planificateur.trouver_co_jurys_disponibles(
                tuteur, creneau['jour'], creneau['heure']
            )

            if co_jurys_disponibles:
                planning.append({
                    "Étudiant": f"{etudiant['Prénom']} {etudiant['Nom']}",
                    "Pays": etudiant['Pays'],
                    "Tuteur": tuteur,
                    "Co-jury": co_jurys_disponibles[0],
                    "Jour": creneau['jour'],
                    "Créneau": creneau['heure'],
                    "Salle": creneau['salle'],
                    "Début": creneau['datetime_debut'],
                    "Fin": creneau['datetime_fin']
                })

        return planning


class PlanificationOptimiseeV2:
    def __init__(self, etudiants, co_jurys, dates, disponibilites, nb_salles, duree):
        self.etudiants = etudiants
        self.co_jurys = co_jurys
        self.dates = dates
        self.disponibilites = disponibilites
        self.nb_salles = nb_salles
        self.duree = duree

        self.tuteurs_referents = list(set([e["Tuteur"] for e in etudiants]))
        self.tous_jurys = list(set(self.tuteurs_referents + co_jurys))
        self.charge_jurys = {jury: 0 for jury in self.tous_jurys}

    def generer_creneaux_uniques(self):
        """Génère tous les créneaux possibles avec identifiants uniques"""
        creneaux = []
        creneau_id = 0

        for jour in self.dates:
            jour_str = jour_fr(jour)
            for periode in [("08:00", "13:00"), ("14:00", "17:20")]:
                debut, fin = periode
                current = datetime.combine(jour, datetime.strptime(debut, "%H:%M").time())
                end = datetime.combine(jour, datetime.strptime(fin, "%H:%M").time())

                while current + timedelta(minutes=self.duree) <= end:
                    fin_creneau = current + timedelta(minutes=self.duree)
                    heure_str = f"{current.strftime('%H:%M')} - {fin_creneau.strftime('%H:%M')}"

                    for salle in range(1, self.nb_salles + 1):
                        creneaux.append({
                            'id': creneau_id,
                            'jour': jour_str,
                            'heure': heure_str,
                            'salle': f"Salle {salle}",
                            'datetime_debut': current,
                            'datetime_fin': fin_creneau,
                            'moment': f"{jour_str}_{heure_str}"
                        })
                        creneau_id += 1

                    current = fin_creneau
        return creneaux

    def est_disponible(self, personne, jour, heure):
        """Vérifie si une personne est disponible à un créneau donné"""
        key = f"{jour} | {heure}"
        return self.disponibilites.get(personne, {}).get(key, False)

    def trouver_co_jurys_disponibles(self, tuteur_referent, jour, heure):
        """Trouve tous les co-jurys disponibles pour un créneau"""
        co_jurys_disponibles = []

        for jury in self.tous_jurys:
            if jury != tuteur_referent and self.est_disponible(jury, jour, heure):
                co_jurys_disponibles.append(jury)

        co_jurys_disponibles.sort(key=lambda x: self.charge_jurys[x])
        return co_jurys_disponibles

    def optimiser_planning_ameliore(self):
        """Algorithme d'optimisation amélioré avec gestion des conflits"""
        creneaux = self.generer_creneaux_uniques()
        planning = []

        creneaux_occupes = set()
        jurys_par_moment = defaultdict(set)

        etudiants_melanges = self.etudiants.copy()
        random.shuffle(etudiants_melanges)

        tentatives_par_etudiant = []

        for idx_etu, etudiant in enumerate(etudiants_melanges):
            tuteur_referent = etudiant["Tuteur"]
            soutenance_planifiee = False
            tentatives = 0

            creneaux_melanges = creneaux.copy()
            random.shuffle(creneaux_melanges)

            for creneau in creneaux_melanges:
                tentatives += 1

                if creneau['id'] in creneaux_occupes:
                    continue

                if not self.est_disponible(tuteur_referent, creneau['jour'], creneau['heure']):
                    continue

                if tuteur_referent in jurys_par_moment[creneau['moment']]:
                    continue

                co_jurys_possibles = self.trouver_co_jurys_disponibles(
                    tuteur_referent, creneau['jour'], creneau['heure']
                )

                co_jurys_libres = [
                    cj for cj in co_jurys_possibles
                    if cj not in jurys_par_moment[creneau['moment']]
                ]

                if co_jurys_libres:
                    co_jury_choisi = co_jurys_libres[0]

                    planning.append({
                        "Étudiant": f"{etudiant['Prénom']} {etudiant['Nom']}",
                        "Pays": etudiant['Pays'],
                        "Tuteur": tuteur_referent,
                        "Co-jury": co_jury_choisi,
                        "Jour": creneau['jour'],
                        "Créneau": creneau['heure'],
                        "Salle": creneau['salle'],
                        "Début": creneau['datetime_debut'],
                        "Fin": creneau['datetime_fin']
                    })

                    creneaux_occupes.add(creneau['id'])
                    jurys_par_moment[creneau['moment']].add(tuteur_referent)
                    jurys_par_moment[creneau['moment']].add(co_jury_choisi)

                    self.charge_jurys[tuteur_referent] += 1
                    self.charge_jurys[co_jury_choisi] += 1

                    soutenance_planifiee = True
                    break

            tentatives_par_etudiant.append(tentatives)

            if not soutenance_planifiee:
                st.warning(
                    f"⚠️ Impossible de planifier {etudiant['Prénom']} {etudiant['Nom']} après {tentatives} tentatives")

        self.afficher_diagnostics(planning, tentatives_par_etudiant)

        return planning, len(self.etudiants) - len(planning)

    def optimiser_avec_genetique(self, utiliser_genetique=False, **params_genetique):
        """Méthode hybride : algorithme classique puis génétique si nécessaire"""
        planning_classique, non_planifies = self.optimiser_planning_ameliore()

        taux_reussite = len(planning_classique) / len(self.etudiants)

        if utiliser_genetique or taux_reussite < 0.8:
            st.info("🧬 Lancement de l'optimisation génétique pour améliorer les résultats...")

            config_genetique = {
                'taille_population': 50,
                'nb_generations': 100,
                'taux_mutation': 0.1,
                'taux_croisement': 0.8,
                **params_genetique
            }

            ag = AlgorithmeGenetique(self, **config_genetique)
            planning_genetique, stats_genetique = ag.evoluer()

            if len(planning_genetique) > len(planning_classique):
                st.success(f"✅ L'algorithme génétique a amélioré les résultats : "
                           f"{len(planning_genetique)} vs {len(planning_classique)} soutenances planifiées")
                return planning_genetique, len(self.etudiants) - len(planning_genetique), stats_genetique
            else:
                st.info("ℹ️ L'algorithme classique reste optimal")
                return planning_classique, non_planifies, None

        return planning_classique, non_planifies, None

    def afficher_diagnostics(self, planning, tentatives_par_etudiant):
        """Affiche des diagnostics détaillés"""
        st.subheader("🔍 Diagnostics de l'optimisation")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Soutenances planifiées", len(planning))
            st.metric("Taux de réussite", f"{len(planning) / len(self.etudiants) * 100:.1f}%")

        with col2:
            if tentatives_par_etudiant:
                st.metric("Tentatives moy. par étudiant", f"{np.mean(tentatives_par_etudiant):.1f}")
                st.metric("Tentatives max.", max(tentatives_par_etudiant))

        with col3:
            charges = list(self.charge_jurys.values())
            if charges:
                st.metric("Charge moyenne des jurys", f"{np.mean(charges):.1f}")
                st.metric("Charge max./min.", f"{max(charges)}/{min(charges)}")

        if planning:
            st.subheader("📊 Répartition de la charge par jury")
            df_charges = pd.DataFrame([
                {"Jury": jury, "Nombre de soutenances": charge}
                for jury, charge in self.charge_jurys.items()
                if charge > 0
            ]).sort_values("Nombre de soutenances", ascending=False)

            fig_charges = px.bar(
                df_charges,
                x="Jury",
                y="Nombre de soutenances",
                title="Nombre de soutenances par jury"
            )
            fig_charges.update_xaxes(tickangle=45)
            st.plotly_chart(fig_charges, use_container_width=True)

    def verifier_conflits(self, planning):
        """Vérifie s'il y a des conflits dans le planning"""
        conflits = []

        creneaux_utilises = defaultdict(list)
        jurys_par_moment = defaultdict(list)

        for idx, soutenance in enumerate(planning):
            moment_salle = f"{soutenance['Jour']}_{soutenance['Créneau']}_{soutenance['Salle']}"
            moment = f"{soutenance['Jour']}_{soutenance['Créneau']}"

            creneaux_utilises[moment_salle].append(idx)
            jurys_par_moment[moment].extend([soutenance['Tuteur'], soutenance['Co-jury']])

        for creneau, indices in creneaux_utilises.items():
            if len(indices) > 1:
                conflits.append(f"Conflit de salle : {creneau} utilisé par {len(indices)} soutenances")

        for moment, jurys in jurys_par_moment.items():
            jurys_uniques = set(jurys)
            if len(jurys) != len(jurys_uniques):
                conflits.append(f"Conflit de jury au moment {moment}")

        return conflits


# ─────────────────────────────────────────────
# Fonction export Excel
# ─────────────────────────────────────────────

def generer_excel(planning, nb_etudiants_total):
    wb = Workbook()

    # ── Feuille 1 : Planning ──
    ws = wb.active
    ws.title = "Planning Soutenances"

    # Styles
    header_fill = PatternFill(start_color="2E4057", end_color="2E4057", fill_type="solid")
    alt_fill    = PatternFill(start_color="EBF2FA", end_color="EBF2FA", fill_type="solid")
    white_fill  = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    data_font   = Font(size=10)
    center      = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    colonnes = ["Étudiant", "Pays", "Tuteur", "Co-jury", "Jour", "Créneau", "Salle"]

    # En-têtes
    for col_idx, col_name in enumerate(colonnes, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.fill      = header_fill
        cell.font      = header_font
        cell.alignment = center
        cell.border    = thin_border

    ws.row_dimensions[1].height = 22

    # Trier le planning par jour puis créneau
    planning_trie = sorted(planning, key=lambda x: (x["Jour"], x["Créneau"], x["Salle"]))

    # Données
    for row_idx, soutenance in enumerate(planning_trie, 2):
        valeurs = [
            soutenance["Étudiant"],
            soutenance["Pays"],
            soutenance["Tuteur"],
            soutenance["Co-jury"],
            soutenance["Jour"],
            soutenance["Créneau"],
            soutenance["Salle"],
        ]
        fill = alt_fill if row_idx % 2 == 0 else white_fill
        for col_idx, valeur in enumerate(valeurs, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=valeur)
            cell.fill      = fill
            cell.font      = data_font
            cell.alignment = center
            cell.border    = thin_border
        ws.row_dimensions[row_idx].height = 18

    # Largeur des colonnes
    largeurs = [28, 14, 22, 22, 28, 20, 12]
    for i, largeur in enumerate(largeurs, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = largeur

    # Figer la première ligne
    ws.freeze_panes = "A2"

    # ── Feuille 2 : Statistiques ──
    ws2 = wb.create_sheet("Statistiques")

    stat_header_fill = PatternFill(start_color="1A535C", end_color="1A535C", fill_type="solid")
    stat_header_font = Font(color="FFFFFF", bold=True, size=11)
    stat_alt_fill    = PatternFill(start_color="F0F7F4", end_color="F0F7F4", fill_type="solid")

    ws2.column_dimensions["A"].width = 30
    ws2.column_dimensions["B"].width = 20

    # Titre
    titre_cell = ws2.cell(row=1, column=1, value="Statistiques du planning")
    titre_cell.font      = Font(bold=True, size=13, color="1A535C")
    titre_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws2.row_dimensions[1].height = 24

    # En-têtes colonnes
    for col_idx, label in enumerate(["Métrique", "Valeur"], 1):
        cell = ws2.cell(row=2, column=col_idx, value=label)
        cell.fill      = stat_header_fill
        cell.font      = stat_header_font
        cell.alignment = center
        cell.border    = thin_border

    # Calculer les stats
    nb_planifies     = len(planning)
    taux_reussite    = nb_planifies / nb_etudiants_total * 100 if nb_etudiants_total > 0 else 0
    salles_utilisees = len(set(s["Salle"] for s in planning))
    jours_utilises   = len(set(s["Jour"]  for s in planning))

    charges_jurys = {}
    for s in planning:
        charges_jurys[s["Tuteur"]]   = charges_jurys.get(s["Tuteur"],   0) + 1
        charges_jurys[s["Co-jury"]]  = charges_jurys.get(s["Co-jury"],  0) + 1

    charge_moy = np.mean(list(charges_jurys.values())) if charges_jurys else 0
    charge_max = max(charges_jurys.values())           if charges_jurys else 0
    charge_min = min(charges_jurys.values())           if charges_jurys else 0

    stats = [
        ("Soutenances planifiées",    nb_planifies),
        ("Total étudiants",           nb_etudiants_total),
        ("Taux de réussite (%)",      f"{taux_reussite:.1f}%"),
        ("Salles utilisées",          salles_utilisees),
        ("Jours utilisés",            jours_utilises),
        ("Charge moyenne des jurys",  f"{charge_moy:.1f}"),
        ("Charge maximale (jurys)",   charge_max),
        ("Charge minimale (jurys)",   charge_min),
    ]

    for row_idx, (metrique, valeur) in enumerate(stats, 3):
        fill = stat_alt_fill if row_idx % 2 == 0 else white_fill
        for col_idx, val in enumerate([metrique, valeur], 1):
            cell = ws2.cell(row=row_idx, column=col_idx, value=val)
            cell.fill      = fill
            cell.font      = data_font
            cell.alignment = center
            cell.border    = thin_border
        ws2.row_dimensions[row_idx].height = 18

    # ── Feuille 3 : Charge par jury ──
    ws3 = wb.create_sheet("Charge par jury")
    ws3.column_dimensions["A"].width = 28
    ws3.column_dimensions["B"].width = 22

    titre3 = ws3.cell(row=1, column=1, value="Répartition de la charge par jury")
    titre3.font      = Font(bold=True, size=13, color="1A535C")
    titre3.alignment = Alignment(horizontal="left", vertical="center")
    ws3.row_dimensions[1].height = 24

    for col_idx, label in enumerate(["Jury", "Nombre de soutenances"], 1):
        cell = ws3.cell(row=2, column=col_idx, value=label)
        cell.fill      = stat_header_fill
        cell.font      = stat_header_font
        cell.alignment = center
        cell.border    = thin_border

    charges_triees = sorted(charges_jurys.items(), key=lambda x: x[1], reverse=True)
    for row_idx, (jury, charge) in enumerate(charges_triees, 3):
        fill = stat_alt_fill if row_idx % 2 == 0 else white_fill
        for col_idx, val in enumerate([jury, charge], 1):
            cell = ws3.cell(row=row_idx, column=col_idx, value=val)
            cell.fill      = fill
            cell.font      = data_font
            cell.alignment = center
            cell.border    = thin_border
        ws3.row_dimensions[row_idx].height = 18

    # Sauvegarde en mémoire
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────
# Importation Excel
# ─────────────────────────────────────────────

st.sidebar.header("📥 Importation Excel")
excel_file = st.sidebar.file_uploader("Importer un fichier Excel", type=["xlsx"])

if excel_file:
    try:
        excel_data = pd.read_excel(excel_file, sheet_name=None)

        if "etudiants" in excel_data:
            etu_df = excel_data["etudiants"]
            required_cols = {"Nom", "Prénom", "Pays", "Tuteur"}
            if required_cols.issubset(etu_df.columns):
                st.session_state.etudiants = etu_df[list(required_cols)].to_dict(orient="records")
                st.sidebar.success("Étudiants importés ✅")
            else:
                st.sidebar.error("La feuille 'etudiants' doit contenir les colonnes : Nom, Prénom, Pays, Tuteur")

        if "co_jurys" in excel_data:
            cj_df = excel_data["co_jurys"]
            if "Nom" in cj_df.columns:
                st.session_state.co_jurys = cj_df["Nom"].dropna().astype(str).tolist()
                st.sidebar.success("Co-jurys importés ✅")
            else:
                st.sidebar.error("La feuille 'co_jurys' doit contenir une colonne 'Nom'")

        if "disponibilites" in excel_data:
            dispo_df = excel_data["disponibilites"]
            required_dispo = {"Personne", "Jour", "Créneau", "Disponible (OUI/NON)"}
            if required_dispo.issubset(dispo_df.columns):
                # Reconstruire le dict de disponibilités
                dispos = {}
                for _, row in dispo_df.iterrows():
                    personne = str(row["Personne"]).strip()
                    jour     = str(row["Jour"]).strip()
                    creneau  = str(row["Créneau"]).strip()
                    dispo    = str(row["Disponible (OUI/NON)"]).strip().upper()
                    if personne not in dispos:
                        dispos[personne] = {}
                    dispos[personne][f"{jour} | {creneau}"] = (dispo == "OUI")
                st.session_state.disponibilites = dispos

                # Extraire les dates uniques depuis les jours présents
                from datetime import datetime as dt_parse
                jours_uniques = dispo_df["Jour"].dropna().astype(str).str.strip().unique()
                dates_parsees = []
                for j in jours_uniques:
                    try:
                        # Format attendu : "lundi 23/06/2025"
                        date_part = j.split(" ", 1)[-1]  # "23/06/2025"
                        dates_parsees.append(dt_parse.strptime(date_part, "%d/%m/%Y").date())
                    except Exception:
                        pass
                if dates_parsees:
                    st.session_state.dates_soutenance = sorted(set(dates_parsees))

                # Reconstruire horaires_par_jour pour l'étape 7
                from datetime import datetime as dt2, timedelta as td2
                duree_val = st.session_state.get("duree_soutenance", 50)
                horaires_par_jour = {}
                for jour_date in st.session_state.dates_soutenance:
                    jour_str = jour_fr(jour_date)
                    creneaux_list = []
                    for debut_s, fin_s in [("08:00", "13:00"), ("14:00", "17:20")]:
                        cur = dt2.combine(jour_date, dt2.strptime(debut_s, "%H:%M").time())
                        end = dt2.combine(jour_date, dt2.strptime(fin_s,   "%H:%M").time())
                        while cur + td2(minutes=duree_val) <= end:
                            fin_c = cur + td2(minutes=duree_val)
                            creneaux_list.append(f"{cur.strftime('%H:%M')} - {fin_c.strftime('%H:%M')}")
                            cur = fin_c
                    horaires_par_jour[jour_str] = creneaux_list
                st.session_state.horaires_par_jour = horaires_par_jour

                nb_personnes = len(dispos)
                nb_creneaux  = sum(len(v) for v in dispos.values())
                st.sidebar.success(f"Disponibilités importées ✅ ({nb_personnes} personnes, {nb_creneaux} créneaux)")
            else:
                st.sidebar.error(
                    "La feuille 'disponibilites' doit contenir : Personne, Jour, Créneau, Disponible (OUI/NON)"
                )

    except Exception as e:
        st.sidebar.error(f"Erreur lors de la lecture du fichier : {e}")

# ─────────────────────────────────────────────
# Étapes
# ─────────────────────────────────────────────

if st.session_state.etape == "etudiants":
    afficher_navigation()
    st.header("Étape 1 : Gestion des étudiants")

    with st.form("ajout_etudiant"):
        col1, col2 = st.columns(2)
        with col1:
            nom    = st.text_input("Nom")
            prenom = st.text_input("Prénom")
        with col2:
            pays   = st.text_input("Pays")
            tuteur = st.text_input("Tuteur")

        if st.form_submit_button("Ajouter étudiant") and all([nom, prenom, pays, tuteur]):
            st.session_state.etudiants.append({
                "Nom": nom, "Prénom": prenom, "Pays": pays, "Tuteur": tuteur
            })
            st.success(f"Étudiant {prenom} {nom} ajouté avec succès")

    if st.session_state.etudiants:
        st.subheader("Liste des étudiants")
        df_etudiants = pd.DataFrame(st.session_state.etudiants)
        st.dataframe(df_etudiants, use_container_width=True)

    if st.button("Passer à l'étape suivante", type="primary"):
        if st.session_state.etudiants:
            st.session_state.etape = "salles"
            st.rerun()
        else:
            st.error("Veuillez ajouter au moins un étudiant")

elif st.session_state.etape == "salles":
    afficher_navigation()
    st.header("Étape 2 : Configuration des salles")
    nb_salles = st.number_input("Nombre de salles disponibles", min_value=1, max_value=10, value=2, step=1)
    if st.button("Valider et continuer", type="primary"):
        st.session_state.nb_salles = nb_salles
        st.session_state.etape = "duree_soutenance"
        st.rerun()

elif st.session_state.etape == "duree_soutenance":
    afficher_navigation()
    st.header("Étape 3 : Durée des soutenances")
    duree = st.number_input("Durée d'une soutenance (minutes)", min_value=30, max_value=120, value=50, step=10)
    if st.button("Valider et continuer", type="primary"):
        st.session_state.duree_soutenance = duree
        st.session_state.etape = "co_jury"
        st.rerun()

elif st.session_state.etape == "co_jury":
    afficher_navigation()
    st.header("Étape 4 : Gestion des co-jurys")

    with st.form("ajout_cojury"):
        nom = st.text_input("Nom du co-jury")
        if st.form_submit_button("Ajouter co-jury") and nom:
            if nom not in st.session_state.co_jurys:
                st.session_state.co_jurys.append(nom)
                st.success(f"Co-jury {nom} ajouté")
            else:
                st.warning("Ce co-jury existe déjà")

    if st.session_state.co_jurys:
        st.subheader("Liste des co-jurys")
        for idx, cj in enumerate(st.session_state.co_jurys):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"👨‍🏫 {cj}")
            with col2:
                if st.button("Supprimer", key=f"cj_suppr_{idx}"):
                    del st.session_state.co_jurys[idx]
                    st.rerun()

    if st.button("Passer à l'étape suivante", type="primary"):
        st.session_state.etape = "dates"
        st.rerun()

elif st.session_state.etape == "dates":
    afficher_navigation()
    st.header("Étape 5 : Dates des soutenances")
    nb_jours = st.number_input("Nombre de jours de soutenances", min_value=1, max_value=5, value=2)
    dates = []
    for i in range(nb_jours):
        date = st.date_input(f"Date du jour {i + 1}", key=f"date_{i}")
        dates.append(date)
    if st.button("Valider les dates", type="primary"):
        st.session_state.dates_soutenance = dates
        st.session_state.etape = "disponibilites"
        st.rerun()

elif st.session_state.etape == "disponibilites":
    afficher_navigation()
    st.header("Étape 6 : Génération des créneaux")
    if st.session_state.dates_soutenance:
        horaires_par_jour = {}
        for jour in st.session_state.dates_soutenance:
            jour_str = jour_fr(jour)
            creneaux = []
            for (debut, fin) in [("08:00", "13:00"), ("14:00", "17:20")]:
                current = datetime.combine(jour, datetime.strptime(debut, "%H:%M").time())
                end     = datetime.combine(jour, datetime.strptime(fin,   "%H:%M").time())
                while current + timedelta(minutes=st.session_state.duree_soutenance) <= end:
                    fin_creneau = current + timedelta(minutes=st.session_state.duree_soutenance)
                    creneaux.append(f"{current.strftime('%H:%M')} - {fin_creneau.strftime('%H:%M')}")
                    current = fin_creneau
            horaires_par_jour[jour_str] = creneaux
        st.session_state.horaires_par_jour = horaires_par_jour
        for jour, slots in horaires_par_jour.items():
            st.subheader(f"📅 {jour}")
            cols = st.columns(min(len(slots), 4))
            for i, slot in enumerate(slots):
                with cols[i % 4]:
                    st.write(f"🕒 {slot}")
        if st.button("Passer à la saisie des disponibilités", type="primary"):
            st.session_state.etape = "disponibilites_selection"
            st.rerun()

elif st.session_state.etape == "disponibilites_selection":
    afficher_navigation()
    st.header("Étape 7 : Saisie des disponibilités")

    # Raccourci si les dispos ont déjà été importées depuis Excel
    if st.session_state.disponibilites:
        nb_p    = len(st.session_state.disponibilites)
        nb_oui  = sum(1 for dicos in st.session_state.disponibilites.values() for v in dicos.values() if v)
        st.success(
            f"✅ Disponibilités déjà importées depuis le fichier Excel — "
            f"**{nb_p} personnes**, **{nb_oui} créneaux disponibles**. "
            f"Tu peux passer directement à la génération du planning."
        )
        col_a, col_b = st.columns([2, 1])
        with col_a:
            if st.button("Générer le planning directement ➜", type="primary"):
                st.session_state.etape = "generation"
                st.rerun()
        with col_b:
            modifier = st.checkbox("Modifier manuellement")
        if not modifier:
            st.stop()

    tous_tuteurs = list(set([e["Tuteur"] for e in st.session_state.etudiants]))
    personnes    = tous_tuteurs + st.session_state.co_jurys
    for personne in personnes:
        st.subheader(f"👨‍🏫 Disponibilités de {personne}")
        if personne not in st.session_state.disponibilites:
            st.session_state.disponibilites[personne] = {}
        for jour, creneaux in st.session_state.horaires_par_jour.items():
            st.markdown(f"**{jour}**")
            all_key      = f"{personne}_{jour}_all"
            all_selected = st.checkbox("Disponible toute la journée", key=all_key)
            cols         = st.columns(min(len(creneaux), 3))
            for i, creneau in enumerate(creneaux):
                with cols[i % 3]:
                    key_dispo = f"{jour} | {creneau}"
                    if all_selected:
                        st.session_state.disponibilites[personne][key_dispo] = True
                        st.checkbox(creneau, value=True, disabled=True, key=f"disabled_{personne}_{i}")
                    else:
                        current_value = st.session_state.disponibilites[personne].get(key_dispo, False)
                        checked = st.checkbox(creneau, value=current_value, key=f"{personne}_{jour}_{i}")
                        st.session_state.disponibilites[personne][key_dispo] = checked
        st.divider()
    if st.button("Générer le planning", type="primary"):
        st.session_state.etape = "generation"
        st.rerun()

elif st.session_state.etape == "generation":
    afficher_navigation()
    st.header("🚀 Génération du planning optimisé")

    col1, col2 = st.columns(2)
    with col1:
        utiliser_genetique = st.checkbox(
            "Forcer l'utilisation de l'algorithme génétique",
            help="L'algorithme génétique sera utilisé automatiquement si l'algorithme classique ne donne pas de bons résultats"
        )
    with col2:
        if utiliser_genetique:
            with st.expander("⚙️ Paramètres avancés"):
                taille_population = st.slider("Taille de la population", 20, 100, 50)
                nb_generations    = st.slider("Nombre de générations",   50, 200, 100)
                taux_mutation     = st.slider("Taux de mutation",       0.05, 0.3, 0.1)

    if st.button("Lancer l'optimisation", type="primary"):
        with st.spinner("Optimisation en cours..."):
            optimiseur = PlanificationOptimiseeV2(
                st.session_state.etudiants,
                st.session_state.co_jurys,
                st.session_state.dates_soutenance,
                st.session_state.disponibilites,
                st.session_state.nb_salles,
                st.session_state.duree_soutenance
            )

            params_genetique = {}
            if utiliser_genetique:
                params_genetique = {
                    'taille_population': taille_population,
                    'nb_generations':    nb_generations,
                    'taux_mutation':     taux_mutation
                }

            planning, non_planifies, stats_genetique = optimiseur.optimiser_avec_genetique(
                utiliser_genetique=utiliser_genetique,
                **params_genetique
            )
            st.session_state.planning_final = planning

        # Statistiques génétiques
        if stats_genetique:
            st.subheader("🧬 Statistiques de l'algorithme génétique")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Générations", stats_genetique['generations'])
            with col2:
                st.metric("Fitness finale", f"{stats_genetique['fitness_finale']:.1f}")
            with col3:
                st.metric("Conflits", stats_genetique['conflits'])
            with col4:
                st.metric("Amélioration",
                          f"+{len(planning) - (len(st.session_state.etudiants) - non_planifies)} soutenances")

            if stats_genetique['historique']:
                import plotly.graph_objects as go

                df_hist      = pd.DataFrame(stats_genetique['historique'])
                fig_evolution = go.Figure()
                fig_evolution.add_trace(go.Scatter(
                    x=df_hist['generation'], y=df_hist['fitness_max'],
                    mode='lines', name='Fitness maximale', line=dict(color='green')
                ))
                fig_evolution.add_trace(go.Scatter(
                    x=df_hist['generation'], y=df_hist['soutenances_max'],
                    mode='lines', name='Soutenances planifiées',
                    yaxis='y2', line=dict(color='blue')
                ))
                fig_evolution.update_layout(
                    title="Évolution de l'algorithme génétique",
                    xaxis_title="Génération",
                    yaxis_title="Fitness",
                    yaxis2=dict(title="Soutenances", overlaying='y', side='right'),
                    height=400
                )
                st.plotly_chart(fig_evolution, use_container_width=True)

        # Vérification des conflits
        if planning:
            conflits = optimiseur.verifier_conflits(planning)
            if conflits:
                st.error("⚠️ Conflits détectés dans le planning :")
                for conflit in conflits:
                    st.write(f"- {conflit}")
            else:
                st.success("✅ Aucun conflit détecté dans le planning")

            st.success(f"Planning généré avec succès ! {len(planning)} soutenances planifiées.")

            if non_planifies > 0:
                st.warning(f"⚠️ {non_planifies} étudiant(s) n'ont pas pu être planifiés.")

            df_planning = pd.DataFrame(planning)

            st.subheader("📋 Planning détaillé")
            st.dataframe(df_planning.drop(['Début', 'Fin'], axis=1), use_container_width=True)

            # Gantt
            if not df_planning.empty:
                st.subheader("📊 Visualisation du planning")
                df_planning["Task"] = df_planning["Étudiant"] + " (" + df_planning["Salle"] + ")"
                fig = px.timeline(
                    df_planning,
                    x_start="Début", x_end="Fin", y="Tuteur", color="Task",
                    title="Planning des soutenances par tuteur",
                    hover_data=["Étudiant", "Co-jury", "Salle", "Pays"]
                )
                fig.update_yaxes(autorange="reversed")
                fig.update_layout(height=600)
                st.plotly_chart(fig, use_container_width=True)

                # Statistiques
                st.subheader("📈 Statistiques")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Soutenances planifiées", len(planning))
                with col2:
                    st.metric("Taux de réussite", f"{len(planning) / len(st.session_state.etudiants) * 100:.1f}%")
                with col3:
                    st.metric("Salles utilisées", df_planning['Salle'].nunique())
                with col4:
                    st.metric("Jours utilisés", df_planning['Jour'].nunique())

                # Répartition par jour
                st.subheader("📅 Répartition par jour")
                repartition = df_planning.groupby(['Jour', 'Salle']).size().reset_index(name='Nombre')
                fig_bar = px.bar(repartition, x='Jour', y='Nombre', color='Salle',
                                 title="Nombre de soutenances par jour et par salle")
                st.plotly_chart(fig_bar, use_container_width=True)

            # ── Export Excel ──
            st.subheader("📥 Export du planning")
            excel_buffer = generer_excel(planning, len(st.session_state.etudiants))
            st.download_button(
                label="📥 Télécharger le planning Excel",
                data=excel_buffer,
                file_name="planning_soutenances.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

        else:
            st.error("❌ Aucune soutenance n'a pu être planifiée. Vérifiez les disponibilités et les contraintes.")

    # Si un planning existe déjà en session, proposer le téléchargement sans relancer
    elif st.session_state.planning_final:
        st.subheader("📥 Export du planning")
        excel_buffer = generer_excel(st.session_state.planning_final, len(st.session_state.etudiants))
        st.download_button(
            label="📥 Télécharger le planning Excel",
            data=excel_buffer,
            file_name="planning_soutenances.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

# ─────────────────────────────────────────────
# Sidebar résumé
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("---")
    st.markdown("### 📊 Résumé")
    st.write(f"**Étudiants :** {len(st.session_state.etudiants)}")
    st.write(f"**Co-jurys :** {len(st.session_state.co_jurys)}")
    st.write(f"**Salles :** {st.session_state.nb_salles}")
    st.write(f"**Durée :** {st.session_state.duree_soutenance} min")

    if st.session_state.dates_soutenance:
        st.write(f"**Dates :** {len(st.session_state.dates_soutenance)} jour(s)")

    st.markdown("---")
    st.markdown("### ℹ️ À propos")
    st.write("Système de planification automatique utilisant l'algorithme glouton ou génétique pour respecter toutes les contraintes.")
    st.markdown("---")
    st.caption("© 2024-2025 - Polytech 4A MAM")