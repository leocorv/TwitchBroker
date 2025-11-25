# TwitchBroker

Script Python chargé de convertir les événements Twitch (EventSub WebSocket) en messages JSON envoyés à un mod Minecraft Fabric via TCP.

## Objectif
Ce broker agit comme couche intermédiaire :
- il écoute les événements Twitch (points de chaîne, rewards custom…)
- il normalise ces événements dans un format JSON simple
- il les envoie via une connexion TCP courte vers le mod Minecraft

Le mod Fabric n’a pas besoin de connaître Twitch.  
Le broker n’a pas besoin de connaître Minecraft.  
Chacun fait son travail.

## Architecture
Twitch EventSub → TwitchBroker (Python) → TCP JSON → Mod Fabric (serveur) -> (Si cote visuel) Fabric (Client)

### Exemple de JSON envoyé
```json
{
  "event_type": "points",
  "event_name": "reward_redeem",
  "value": "Nom de la récompense"
}

```

### Configuration (.env)

Le script utilise un fichier ```.env``` à créer dans le dossier du projet :
```INI
TWITCH_CLIENT_ID=ton_client_id
TWITCH_CLIENT_SECRET=ton_secret
TWITCH_USERNAME=nerixtv
```

### Installation

1. Créer un virtualenv (optionnel mais conseillé)
2. Installer les dépendances : 
```linux
pip install -r requirements.txt
```

### Exécution
Lance simplement :
```linux
python broker.py
```
Le script ouvre un EventSub WebSocket, écoute les redeems, et publie les events au mod Fabric.


---

### Licence
All Rights Reserved.


