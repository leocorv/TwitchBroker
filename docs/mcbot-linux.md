# MCBOT — socle de contrôle collectif Linux

## État de cette branche

Prototype exécutable du moteur et simulateur JSONL, Python 3.10+ et bibliothèque
standard uniquement. Il ne se connecte pas encore au chat et ne pilote pas encore
Minecraft. Le broker de récompenses existant reste indépendant.

```bash
python3 -m unittest discover -s tests -v
python3 -m mcbot < examples/control.jsonl
```

La démo envoie plusieurs messages avant un tick : les décisions résultent du lot,
jamais du rejeu séquentiel des messages. La dernière sortie montre l'arrêt après
trois secondes de silence, avec le slot et l'intention sprint conservés.

## Architecture cible

1. Adaptateur Twitch : identité stable, identifiant unique de message, filtrage
   des livraisons anciennes et horodatage local monotone à réception.
2. Parseur et moteur Python : lots glissants indépendants par axe, tick à 100 ms.
3. Adaptateur Minecraft client : appliquer l'état complet des touches, la vitesse
   caméra et les impulsions uniques. Le moteur ne connaît pas le système graphique.
4. Overlay : afficher les scores, touches réellement appliquées et état du client.

Pour Linux, la cible proposée est un petit mod **client Fabric** dans la vraie
instance Minecraft filmée. Le protocole local et sa version restent à implémenter.
Cela permettra de traiter les commandes dans le client sans coupler le moteur à
une simulation de clavier du bureau. Un serveur Minecraft seul ne fournit pas
la vue du personnage à diffuser. La version Minecraft/Fabric sera fixée lors de
l'intégration, sans reprendre arbitrairement celle de SurvieInteract.

Sur la machine Linux : service Python + client graphique Minecraft + capture OBS.
Le GPU sert au rendu/encodage ; aucun modèle IA n'est nécessaire à l'arbitrage.
Le simulateur fonctionne sans GPU, sans affichage, sans Twitch et sans réseau.

## Règles implémentées

- Tous les participants ont le même poids ; aucun groupe ni rôle technique.
- Plusieurs messages récents d'une même personne peuvent contribuer, avec une
  limite de trois messages acceptés par seconde et par identité.
- Une seule contribution par axe et par message, même si une touche est répétée.
- Syntaxe V1 stricte : message composé exclusivement de commandes reconnues.
  `w right hit slot3` fonctionne, `w lol` est ignoré. Choix volontaire pour éviter
  qu'une discussion contenant `a` ou `right` fasse bouger le personnage.
- Deux ordres opposés dans le même message rendent cet axe neutre.
- Axes indépendants : w/s, d/a, left/right, up/down ; diagonales possibles.
- Fenêtre = clamp(12 / débit accepté par axe, 0,3 s, 1,2 s).
  Le débit utilise les cinq dernières secondes. Les messages rejetés et les
  viewers silencieux n'entrent pas dans le calcul.
- Poids de récence = 2^(-2 × âge / fenêtre). Les pourcentages de l'overlay
  correspondent à ces poids, pas à des pourcentages de viewers.
- Il faut 15 points d'avance sur le second choix, rapportés au total des poids.
  En dessous : neutre, y compris à égalité. Paramètre expérimental.
- Expiration indépendante de chaque vote : mouvement 1 s, caméra 350 ms,
  minage 700 ms. L'expiration est limitée aussi par la fenêtre adaptative.
  Une nouvelle commande sur un autre axe ne ranime jamais une vieille direction.
- Maintien renouvelé sans relâchement si la touche reste gagnante entre les ticks.
  L'adaptateur futur appliquera la différence entre états, sans retaper la touche.
- Caméra : vitesse signée normalisée ; l'adaptateur multipliera par une vitesse
  maximale et le temps écoulé. Elle ne dépendra pas du nombre de ticks par seconde.
- `hit`, `use`, `drop`, `jump` : impulsions uniques ; le lot de leur canal est
  consommé après décision, perdants compris. `hit/use/mine` partagent un canal ;
  `jump` et `drop` sont indépendants. Cooldowns spécifiques à prévoir côté client.
- `sprint/walk`, `sneak/stand` : états ON/OFF persistants et idempotents. Pas de
  bascule aveugle à chaque message. Sneak suspend l'application réelle du sprint.
- `slot1` à `slot9` : choix collectif pondéré, état persistant, pas une file FIFO.
- Après silence : ni déplacement, ni caméra, ni clic ; sneak reste appliqué
  s'il a été activé. Il faut distinguer cette pause normale d'un arrêt d'urgence.
- Déconnexion/arrêt d'urgence : `reset()` efface aussi sprint, sneak et slot.

Les valeurs restent à régler par essais ; elles ne constituent pas une preuve
de jouabilité en présence de la latence réelle Twitch/vidéo. `ww/www` et les
transactions d'inventaire ne sont pas implémentés dans ce socle.

## Contrat de sortie provisoire

`keys` est l'ensemble complet à maintenir ; une touche absente doit être relâchée.
`camera` contient yaw/pitch dans [-1, 1]. `pulses` contient seulement les nouvelles
actions du tick ; `slot` contient le choix persistant. `channels` sert au diagnostic.

Avant connexion au jeu, ajouter une enveloppe avec version, numéro de séquence,
session, durée de validité courte et identifiant des impulsions. Le client doit
refuser les frames anciennes, dédupliquer les impulsions, libérer toutes les
touches si le heartbeat disparaît et demander une nouvelle session après reprise.
Transport local uniquement au départ, authentifié ; aucun port exposé publiquement.

Un écran ouvert, une perte de monde ou une déconnexion doit suspendre les contrôles.
Les opérations d'inventaire seront des transactions avec vérification du conteneur,
pas des clics calculés sur des coordonnées d'écran.

## Suite de l'implémentation

1. Fixer version Minecraft, méthode de lancement et capture Linux.
2. Implémenter l'adaptateur chat avec reconnexion, filtrage des messages anciens
   et reset de sécurité ; vérifier les scopes nécessaires à ce moment-là.
3. Implémenter le mod client, le protocole local, watchdog et retour d'état.
4. Tester avec 1, 5, 20 et 100 participants simulés puis avec le vrai stream.
5. Régler seuils, durée des appuis et cooldowns, puis ajouter l'inventaire.

Limites : déduplication bornée à 60 s, stockage borné (rejet en cas de saturation),
parcours en mémoire à chaque tick. Le débit de simulation n'est pas un benchmark
de production ; optimiser après mesure. Le moteur doit être appelé depuis une
seule boucle d'événements et les ticks doivent continuer même sans message.
