# Confronto: Taiga, Jira e Orangescrum



## 1. Taiga

### API

API REST, versione 1, tutto sotto `/api/v1/`
`https://api.taiga.io/api/v1`

**Autenticazione.** Due modi:

- **Token normale**: si fa un POST su `/api/v1/auth` con username e password e si riceve un token, da mettere poi nell'header `Authorization: Bearer <token>`. Il token **scade** e si rinnova con `/api/v1/auth/refresh`.
- **Token applicativo**: pensato per app esterne. L'app viene registrata, si chiede un codice di autorizzazione, lo si valida e si ottiene un token cifrato (JWE) da decifrare con una chiave. L'header diventa `Authorization: Application <token>`.

Per la pipeline il *Token Normale* potrebbe essere sufficiente, rimane il problema che il token scade, bisogna quinid rifare il login per ogni build. Su OpenProject il token non ha scadenza

**Cosa si può fare.** L'API copre: progetti, epiche, user story, task, issue, milestone (sprint), wiki, allegati, cronologia e commenti, utenti, ruoli e membership. Ci sono anche:

- **webhook** (`/api/v1/webhooks`), con log delle chiamate, test e rinvio manuale
- **export/import** di un intero progetto come dump;
- **importer** già pronti da Trello, GitHub e Jira.

### Ruoli e permessi

I ruoli sono **per progetto**, non globali, e si gestiscono via API (`/api/v1/roles`). Ogni ruolo ha una lista di permessi definibili. Un membro però **può avere un solo ruolo per progetto**, non più di uno. Esistono poi i permessi per i progetti pubblici, cioè cosa può vedere chi non è membro.

### Community e licenza

Open source, sviluppato da *Kaleidos*. La licenza è passata da AGPL 3.0 a MPL 2.0.
Esiste  una repository `taiga-docker` ufficiale con docker compose per utilizzarlo su proprio server. Necessari (in teoria) PostgreSQL e RabbitMQ. Il supporto è community: forum ufficiale e issue su GitHub.

### Interoperabilità

È il più aperto dei tre su questo punto, possiede importer nativi da **Trello, GitHub e Jira**, export/import di progetti interi, webhook configurabili e librerie di terze parti.

---

## 2. Jira

### API

API REST, versione 3, la più completa e documentata.

**Autenticazione.** Tre strade:

- **Basic auth con API token**: email dell'account Atlassian come utente e token come password `https://<sito>.atlassian.net/rest/api/3/...`
- **OAuth 2.0 (3LO)**: per app, con scope e token di accesso `https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/...`
- **Forge e Connect**: per le app pubblicate sul marketplace.

**Cosa si può fare.** Per le issue: creazione, modifica, cancellazione, ricerca con JQL, transizioni di stato, allegati. 

Webhook per gli eventi (issue create/modificate, commenti, sprint, versioni) e oer Jenkins esiste un **plugin ufficiale** che aggiunge commenti e cambia stato alle issue selezionate con una query JQL.
Possibile integrazione sia manuale che con il plugin

### Ruoli e permessi


- **permessi globali**, validi su tutto l'ambiente
- **permessi di progetto** associa le azioni (creare, modificare, chiudere, assegnare) a utenti, gruppi o ruoli;
- **permessi a livello di singola issue** 

I ruoli predefiniti sono Administrators, Developers e Users, ma se ne possono creare altri. Tutto questo è gestibile anche via API, con endpoint dedicati a permission scheme e project role.

### Community e licenza

**Jira non è open source**, "è un prodotto commerciale Atlassian" 

- **Jira Server** (la vecchia versione installabile) è fuori supporto da febbraio 2024;
- **Jira Data Center** (l'attuale self-hosted) non è più vendibile a nuovi clienti da **marzo 2026** e si prevede la chiusura il **marzo 2029**
- **Jira Cloud** ha  un piano gratuito fino a **10 utenti** e **2 GB di spazio**, **supporto solo community**


### Interoperabilità

 Jira importa direttamente da **Trello, Asana, ClickUp e monday**, e da qualsiasi altro sistema via CSV o JSON. In più c'è il marketplace e i webhook per collegarlo ad altro.

---

## 3. Orangescrum

Ogni edizione è differente 
### API

- **Community Edition (quella open source): l'API non c'è.** la Developer API non è inclusa nell'edizione community.
- **Cloud**: Developer API REST con 59 endpoint (progetti, task, timelog, utenti, test case, difetti, checklist), inclusa però solo nel piano "Premium Unlimited". Le chiavi si chiedono all'account manager. Tutte le chiamate sono in POST sotto `/api/v1/partner/`, anche le letture, perché il corpo della richiesta è cifrato; l'autenticazione è con header `X-API-KEY`. Esiste anche un server MCP con 72 strumenti, per collegare client AI.
- **Self-Hosted**: l'accesso API è un **plugin a pagamento** ("API Access"), che aggiunge REST sotto `/api/v1`, un endpoint GraphQL, chiavi con scope, webhook firmati e rate limit.

Servirebbe il cloud a pagamento o il plugin.

### Ruoli e permessi

Nella Community Edition ci sono **solo due ruoli**, Admin e User, senza matrice dei permessi né ruoli personalizzati. Il controllo degli accessi passa quasi solo dall'appartenenza ai progetti: un utente vede un progetto solo se ne è membro, mentre gli admin vedono tutto e non c'è modo di nascondere loro qualcosa. Mancano anche SSO, LDAP/SAML, account cliente/ospite, team e audit degli utenti.

**Nelle edizioni a pagamento ci sono invece ruoli personalizzati, team e unità organizzative.**

### Community e licenza

La Community Edition è stata rilasciata come open source ad **agosto 2026** sotto **AGPL v3**, su GitHub. È self-hosted, senza chiave di licenza e senza limiti di utenti, progetti o spazio. Stack: PHP 8.2+, CakePHP 4.6, PostgreSQL 16, installabile con docker compose. Supporto via issue su GitHub e gruppo Google.
Ci sono progetti, task, sottotask, milestone, commenti, allegati, checklist ed ore registrate a mano. Non ci sono board agili, Gantt, gestione risorse, reportistica e **nessuna integrazione** (niente GitHub, Slack, Google Calendar, SSO).

### Interoperabilità

- **Community Edition**: nessuna integrazione.
- **Cloud**: GitHub, Slack, Zapier (e tramite Zapier si arriva a Trello, Asana, Teams e altri), OneDrive, Google Calendar, Azure DevOps.
- **Self-Hosted**: è l'unica edizione con un livello CI/CD. Legge lo stato delle build da **Jenkins**, GitLab CI, GitHub Actions e Bitbucket Pipelines e lo mostra sul singolo work item; permette di creare branch dal task e di bloccare il merge di una pull request finché il task non raggiunge lo stato giusto. Gli eventi della pipeline arrivano via webhook.


---

## 4. Confronto

| | Taiga | Jira | Orangescrum |
|---|---|---|---|
| API | REST v1, completa | REST v3, molto completa | solo a pagamento (cloud premium o plugin) |
| Autenticazione | token con scadenza + refresh, o token applicativo | API token (basic) o OAuth 2.0 | chiave API, richieste cifrate |
| Commento via API | sì | sì, endpoint dedicato | solo con API a pagamento |
| Webhook | sì | sì | solo nelle edizioni a pagamento |
| Ruoli | per progetto, personalizzabili, permessi granulari (un ruolo per membro) | tre livelli, permission scheme, ruoli e gruppi | due ruoli fissi nella versione free |
| Licenza | open source (MPL 2.0) | commerciale | AGPL v3 solo la Community Edition |
| Self-hosting | sì, docker | di fatto no per i nuovi (solo cloud) | sì, docker |
| Costo d'ingresso | zero | gratis fino a 10 utenti, in cloud | zero, ma senza API |
| Import da altri sistemi | Trello, GitHub, Jira + dump | Trello, Asana, ClickUp, monday, CSV, JSON | solo via Zapier (cloud) |
| Integrazione CI/CD | via API e webhook, da costruire | plugin Jenkins ufficiale | livello CI/CD nativo (solo self-hosted a pagamento) |

---

## 5. Conclusioni

**Taiga è l'alternativa più simile a OpenProject.** È open source, si installa sul proprio server, ha un'API completa e gratuita, ruoli configurabili e importa direttamente da Trello, GitHub e Jira. Bisogna però gestire  il token che scade.

**Jira è il più potente ma ancheil meno adatto.** L'API e il modello dei permessi sono i migliori dei tre e per Jenkins esiste un plugin ufficiale ma non è open source e dal 2026 usabile solo con il cloud di Atlassian.

**Orangescrum va preso per quello che è**: la versione libera è un tracker di task semplice, senza API e senza integrazioni,  le funzioni di API, webhook, collegamento con Jenkins sono tutte a pagamento.

**Una nota sui ruoli**, volendo tenere il Product Owner e lo sviluppatore con poteri diversi, Taiga e Jira lasciano questa possibile  distinzione con ruoli e permessi, Orangescrum nella versione libera no.


---

## Fonti

- Taiga REST API: https://docs.taiga.io/api.html
- Licenza di Taiga: https://community.taiga.io/t/whats-taigas-open-source-license/138
- Installazione self-hosted: https://github.com/taigaio/taiga-docker
- Jira Cloud REST API v3: https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
- Autenticazione Jira: https://developer.atlassian.com/cloud/jira/platform/security-overview
- Permessi Jira: https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-permission-schemes/
- Prezzi e licenze Jira: https://www.atlassian.com/software/jira/pricing
- Import in Jira da altri sistemi: https://support.atlassian.com/jira-cloud-administration/docs/migrate-from-other-issue-trackers/
- Orangescrum Community Edition: https://helpdesk.orangescrum.com/guide/community/get-started/introduction
- Ruoli nella Community Edition: https://helpdesk.orangescrum.com/guide/community/usage/users-and-roles
- Developer API di Orangescrum: https://helpdesk.orangescrum.com/guide/api/introduction
- Integrazione Jenkins di Orangescrum: https://www.orangescrum.com/integrations/jenkins

