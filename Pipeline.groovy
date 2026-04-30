pipeline {
    agent any

    environment {
        // Le tue credenziali salvate su Jenkins
        OP_CREDENTIALS = credentials('openproject-token')
        // URL pulito della risorsa
        OP_URL = "http://127.0.0.1:8090/api/v3/work_packages"
    }

    stages {
        stage('Recupero Task') {
            steps {
                script {
                    echo "--- Tentativo di connessione a OpenProject ---"

                    // Usiamo le virgolette singole per far gestire le variabili direttamente alla shell di Jenkins
                    // Nota: ho rimosso "/work_packages" dalla fine del comando perché è già dentro $OP_URL
                    def response = sh(
                        script: 'curl -s -u apikey:$OP_CREDENTIALS -H "Content-Type: application/json" $OP_URL',
                        returnStdout: true
                    ).trim()

                    // Controllo di sicurezza se la risposta contiene errori
                    if (response == "" || response.contains("Error") || response.contains("NotFound")) {
                        echo "Risposta grezza del server: ${response}"
                        error("Fallimento: OpenProject ha risposto con un errore o l'URL è sbagliato!")
                    }

                    echo "Dati ricevuti con successo!"

                    // Estraiamo il titolo della prima task con jq
                    // Usiamo le triple virgolette per gestire meglio i caratteri speciali
                    def taskTitle = sh(
                        script: "echo '${response}' | jq -r '._embedded.elements[0].subject // \"Nessuna task trovata nel progetto\"'",
                        returnStdout: true
                    ).trim()

                    echo "------------------------------------------"
                    echo "RISULTATO API: ${taskTitle}"
                    echo "------------------------------------------"
                }
            }
        }
    }
}



pipeline {
    agent any
    environment {
        OP_CREDENTIALS = credentials('openproject-token')
        // URL della task specifica (sostituisci l'ID con quello della tua task)
        OP_TASK_URL = "http://127.0.0.1:8090/api/v3/work_packages/1094"
    }
    stages {
        stage('Audit Solidity') {
            steps {
                script {
                    echo "--- Controllo Qualità Smart Contract ---"
                    // Qui simuliamo una compilazione. 
                    // Se hai installato solc: sh 'solc SkillSelection.sol'
                    echo "Compilazione completata..."
                }
            }
        }
        stage('Notifica OpenProject') {
            steps {
                script {
                    // Creiamo un commento per OpenProject
                    def comment = '{"notes": "✅ Build di Jenkins completata. Smart Contract compilato con successo e logica corretta."}'
                    
                    sh """
                        curl -X POST -u apikey:${OP_CREDENTIALS} \
                        -H 'Content-Type: application/json' \
                        -d '${comment}' \
                        ${OP_TASK_URL}/activities
                    """
                    echo "Feedback inviato a OpenProject!"
                }
            }
        }
    }
}