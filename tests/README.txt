<<<<<<< HEAD
Buongiorno professoressa, le mando intanto i risultati delle prove che ho fatto, il report inizio a scrivere e glielo mando appena finito. Ho provato diverse operazioni via API: elencare i progetti, leggere un elemento, crearne uno, cambiargli stato, caricare e scaricare un allegato, scrivere un commento. Tutte le operazioni su OpenProject, Taiga e Jira (orangescrum dovrei pagare un abbonamento per poter ottenere l'API quindi non penso sia possibile utilizzarlo). Ogni prova l’ho fatta due volte, una con un utente admin e una con un utente Lettore, per vedere se i permessi vengono rispettati. Funzionano tutte su tutti e tre, e i ruoli vengono rispettati con però alcune differenze nel comportamento. Su OpenProject, prima di poter cambiare stato, ho dovuto impostrae il Workflow per quel ruolo, mentre Taiga e Jira funzionano appena creato il progetto. Su Jira invece i permessi si SOMMANO, nel senso che nel progetto "Pubblico" anche in "Viewer" poteva modificare dato che il progetto era aperto a tutti. Dopo averlo reso Private il ruolo “Viewer” non può modificare nulla ma può comunque caricare allegati, opzione che sugli altri due siti è bloccata.
Nel report creo una tabella  con tutte le varie comparazioni, per ora le invio un file di testo dove ho messo tutti i risultati ottenuti per ogni utente.
=======
I 4 file presenti enlla directory sono:

BaseTest.sol
Con tutto quello che serve agli altri tre file, come la situazione di partenza, i messaggi di errore dei contratti e i controlli che
si ripetono sempre. Gli altri tre contengono i test veri, divisi per argomento. Ho cercato di
coprire tutti i casi che possono capitare davvero.

NFTSkill_test.sol (6 test)
Le competenze, come si leggono e chi ha i permessi di  inserirle

Candidatura_test.sol (10 test)
L'apertura della selezione e le candidature, chi risulta idoneo ed entro quando
ci si puo' candidare

Selezione_test.sol (10 test)
La lista degli idonei e le assunzioni, chi puo' vederla, quando, e chi si puo'
assumere

>>>>>>> 5c1dcdb78b392b9e3ad66834d59cc04029ab451e
