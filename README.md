# Planification Optimisée des Soutenances de Stage

Application développée pour automatiser la planification des soutenances de stage à **Polytech Lyon** : affectation des étudiants, tuteurs, co-jurys, salles et créneaux horaires, sous contraintes de disponibilités.

# Le problème 

Planifier 180 soutenances à la main, c'est un casse-tête : chaque étudiant a un tuteur référent, il faut lui trouver un co-jury disponible au même moment, une salle libre, tout en évitant les conflits d'agenda et en équilibrant la charge de travail entre les jurys. Fait manuellement, ça prend des heures et le résultat est rarement optimal.

## Ce que fait l'application

Une interface Streamlit guide l'utilisateur en 8 étapes :

1. Saisie des étudiants et de leurs tuteurs référents (à la main ou via import d'un fichier Excel)
2. Configuration des salles disponibles
3. Définition de la durée d'une soutenance
4. Liste des co-jurys potentiels
5. Choix des dates de soutenance
6. Génération des créneaux horaires
7. Saisie des disponibilités de chaque jury
8. Génération automatique du planning optimisé

## Comment ça marche

Le cœur du projet est un moteur d'optimisation à deux niveaux :

- **Algorithme glouton** : une première passe rapide qui essaie d'assigner chaque étudiant à un créneau valide, en priorisant les tuteurs ayant le plus d'étudiants.
- **Algorithme génétique** (si le taux de réussite du glouton est insuffisant) : population de solutions, sélection par tournoi, croisement et mutation adaptative, avec une fonction de fitness qui pénalise les conflits et récompense :
  - le taux de soutenances planifiées,
  - l'équilibrage de charge entre les jurys,
  - le regroupement des créneaux d'un même tuteur (moins de temps morts),
  - l'alternance matin/après-midi,
  - l'utilisation optimale des salles.

Le calcul des temps morts prend même en compte la pause déjeuner pour ne pas fausser les statistiques.

## Stack technique

- **Python**
- **Streamlit** — interface web
- **Pandas / NumPy** — manipulation de données
- **Plotly** — visualisation du planning et des statistiques
- **NetworkX** — structures de graphes pour la gestion des contraintes

## Lancer le projet

```bash
pip install -r requirements.txt
streamlit run plan.py
```

## Statut

Projet terminé et fonctionnel.
