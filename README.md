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
- adresses Modbus proposées automatiquement depuis la plage configurée, avec indication **disponible / déjà utilisée**
- saisie manuelle d'une adresse conservée tant qu'elle appartient à la plage configurée
- listes d'unités, `device_class` et `state_class` avec saisie personnalisée possible
- déplacement simultané de plusieurs points vers une même section ou sous-section
- gestion complète des sections : renommer, déplacer ou fusionner une section et toute sa hiérarchie
- détection des doublons de sections dus à la casse, aux espaces, à la ponctuation ou à un nom très proche
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
- diagnostics de communication sur le WAGO principal

## Diagnostics du WAGO principal

Quatre entités de diagnostic sont créées directement sur le contrôleur WAGO :

- **Dernière communication réussie** — date/heure de la dernière lecture Modbus complète réussie
- **Durée de communication** — durée du dernier cycle de communication, en millisecondes
- **Échecs de communication consécutifs** — compteur remis à zéro après une lecture réussie
- **Automate en ligne** — capteur binaire de connectivité basé sur le résultat du dernier cycle Modbus

Les diagnostics restent disponibles lorsque la communication tombe. `Automate en ligne` passe donc à **OFF** au lieu de devenir lui-même indisponible. L'intégration se charge également lors d'un redémarrage de Home Assistant si le WAGO est momentanément hors ligne ; les points métier sont alors indisponibles, mais les diagnostics restent visibles jusqu'au retour de la communication.

## Installation HACS

Ajoutez `https://github.com/jptstar/wago_comm` comme dépôt personnalisé HACS de type **Intégration**.

Installez ensuite **WAGO 750-8212 PFC200**, redémarrez Home Assistant et ajoutez l'intégration depuis **Paramètres → Appareils et services → Ajouter une intégration**.

### Versionnement HACS

Les versions sont publiées sous forme de **GitHub Releases**. Un workflow GitHub crée automatiquement la release correspondant à la valeur `version` du `manifest.json` à chaque changement de version. La branche `main` est masquée dans le sélecteur HACS afin que les installations suivent les releases publiées.

Si le dépôt a été installé avant la mise en place des Releases et que HACS suit encore `main`, effectuez une migration unique : **HACS → WAGO 750-8212 PFC200 → menu ⋮ → Retélécharger → Besoin d'une autre version ? → sélectionner la dernière version `0.1.x`**. Les mises à jour suivantes seront ensuite détectées normalement.

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
2. table Modbus ;
3. adresse Modbus ;
4. format du registre si nécessaire ;
5. paramètres spécifiques au type choisi.

À l'étape **Adresse Modbus**, l'intégration construit la liste à partir de la plage mémoire configurée. Chaque adresse est marquée **disponible**, **adresse actuelle** ou **déjà utilisée** avec le nom des points concernés. La saisie manuelle reste possible.

Pour les capteurs et nombres, les unités courantes sont proposées dans une liste déroulante avec saisie libre. Les classes d'appareil sont proposées depuis les valeurs connues par Home Assistant ; les capteurs proposent aussi les `state_class` disponibles. Une valeur personnalisée peut toujours être saisie.

Chaque étape propose **Retour** pour revenir à l'étape précédente sans devoir quitter complètement la configuration.

Par exemple, un `number` affiche facteur, offset, unité, minimum, maximum, pas et classe d'appareil, tandis qu'un `button` affiche uniquement les paramètres de commande et d'impulsion.

Une nouvelle sous-section se crée en choisissant une section parente. Les sections sont dérivées des points : quand le dernier point d'une section est supprimé ou déplacé, l'appareil de section vide est nettoyé au rechargement.

### Déplacer plusieurs points

Dans **Configurer → Points Modbus → Déplacer plusieurs points**, sélectionnez plusieurs entités dans la liste puis choisissez :

- une section ou sous-section existante ;
- **WAGO principal** pour retirer leur section ;
- **Nouvelle section / sous-section** pour créer une destination à la volée.

La nouvelle section est appliquée à tous les points sélectionnés en une seule opération. Les anciennes sections devenues vides sont ensuite supprimées automatiquement.

## Gestion des sections

Dans **Configurer → Gérer les sections**, chaque section et sous-section affiche le nombre de points qu'elle contient, y compris ses enfants.

Une section peut être :

- renommée ;
- déplacée sous une autre section ;
- fusionnée avec une section existante ;
- déplacée vers le WAGO principal.

L'opération s'applique automatiquement à tous ses points et sous-sections. L'ancienne section disparaît dès qu'elle est vide.

Pour éviter les doublons comme `Filtration Puit`, `Filtration. Puit` ou des variantes de casse/ponctuation, les nouveaux noms sont comparés aux sections existantes. Les équivalents de ponctuation/casse réutilisent la section existante ; les noms très proches déclenchent un avertissement.

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

**0.1.7**
