# WAGO 750-8212 PFC200 — Home Assistant

Intégration Home Assistant locale pour exposer un **WAGO 750-8212 PFC200** via **Modbus/TCP**, sans Node-RED ni MQTT intermédiaire.

La particularité de l'intégration est que les entités ne sont pas codées en dur : la table Modbus est entièrement configurable depuis Home Assistant et peut être remplie rapidement par import CSV.

## Fonctionnalités

- Modbus/TCP 100 % local
- configuration et reconfiguration de l'adresse IP, du port et de l'Unit ID
- timeout, délai de reconnexion et intervalle d'interrogation configurables
- définition des quatre plages mémoire Modbus : Coils, Discrete Inputs, Holding Registers et Input Registers
- jusqu'à **100 points configurables**
- ajout, modification, duplication et suppression depuis Home Assistant
- déplacement simultané de plusieurs points vers une même section ou sous-section
- navigation **Retour** dans l'assistant de configuration des points
- import et export CSV depuis l'interface Home Assistant
- regroupement des lectures par blocs Modbus
- sections et sous-sections hiérarchiques (`Parent / Enfant`)
- sélection d'une section existante ou création d'une nouvelle depuis l'éditeur
- suppression automatique des sections et sous-sections devenues vides
- formulaires dynamiques : seuls les paramètres utiles au type d'entité choisi sont affichés
- `sensor`, `binary_sensor`, `switch`, `number`, `button`, `select`
- `bool`, `uint16`, `int16`, `uint32`, `int32`, `float32`
- facteur, offset, précision, min, max, pas et unité
- extraction d'un bit dans un registre
- inversion booléenne
- ordre des octets et des mots
- commandes impulsionnelles
- relecture automatique après écriture
- identifiant stable par point

## Installation HACS

Ajoutez `https://github.com/jptstar/wago_comm` comme dépôt personnalisé HACS de type **Intégration**.

Installez ensuite **WAGO 750-8212 PFC200**, redémarrez Home Assistant et ajoutez l'intégration depuis **Paramètres → Appareils et services → Ajouter une intégration**.

## Mémoire Modbus par défaut

Les valeurs correspondent à la table CODESYS fournie :

| Table | Start | Taille | Plage |
|---|---:|---:|---:|
| Coils | 0 | 48 | 0–47 |
| Discrete Inputs | 50 | 8 | 50–57 |
| Holding Registers | 60 | 40 | 60–99 |
| Input Registers | 100 | 3 | 100–102 |

Elles restent modifiables dans **Configurer → Mémoire Modbus**.

## Éditeur de points

L'ajout ou la modification d'un point se fait sous forme d'assistant :

1. identité, type d'entité et section ;
2. table Modbus et adresse ;
3. format du registre si nécessaire ;
4. paramètres spécifiques au type choisi.

Chaque étape propose désormais **Retour** pour revenir à l'étape précédente sans devoir quitter complètement la configuration.

Par exemple, un `number` affiche facteur, offset, unité, minimum, maximum et pas, tandis qu'un `button` affiche uniquement les paramètres de commande et d'impulsion.

Une nouvelle sous-section se crée en choisissant une section parente. Les sections sont dérivées des points : quand le dernier point d'une section est supprimé ou déplacé, l'appareil de section vide est nettoyé au rechargement.

### Déplacer plusieurs points

Dans **Configurer → Points Modbus → Déplacer plusieurs points**, sélectionnez plusieurs entités dans la liste puis choisissez :

- une section ou sous-section existante ;
- **WAGO principal** pour retirer leur section ;
- **Nouvelle section / sous-section** pour créer une destination à la volée.

La nouvelle section est appliquée à tous les points sélectionnés en une seule opération. Les anciennes sections devenues vides sont ensuite supprimées automatiquement.

## Import CSV

Le fichier `examples/wago_points.csv` est prérempli avec les points explicitement présents dans les flows Node-RED transmis.

Dans Home Assistant : **Configurer → Importer un CSV → choisir le fichier → Remplacer/Fusionner → vérifier → confirmer**.

Le CSV est validé avant import : plages mémoire, types, écritures interdites, min/max/pas, facteur, bits, IDs, limite de 100 points, etc.

Pour une hiérarchie, la colonne `section` peut contenir par exemple `Arrosage gazon / Terrasse`.

Le menu **Exporter le CSV** écrit la table courante dans `/config/www/wago_exports/`, accessible via `/local/wago_exports/`.

## Conversion

`valeur HA = valeur brute × scale + offset`

L'écriture applique automatiquement la conversion inverse.

## Point à vérifier

Les flows fournis utilisent le **Coil 21 à la fois pour “Gazon pool house” et “GG haies chemin”**. Le CSV conserve volontairement les deux lignes et l'import affichera un avertissement. Vérifiez l'adresse réelle dans CODESYS avant utilisation en production.

## Version

**0.1.2**
