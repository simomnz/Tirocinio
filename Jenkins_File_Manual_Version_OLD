// Pipeline di Verifica delle USER STORY: criteri di accettazione scritti in OpenProject, Taiga o Jira
// Codice da verificare da una repository Github

pipeline {                                  
    agent any                               // crea lo spazio di lavoro

    parameters {                            // parametri in input

        choice(
            name: 'SYSTEM',
            choices: ['openproject', 'taiga', 'jira'],   // menu a tendina
            description: 'Dove sono scritti i criteri di accettazione'
        )
        string(
            name: 'TASK',
            defaultValue: '1115',           // per prova
            description: 'Identificativo della task'
        )
        string(
            name: 'REPOSITORY',
            defaultValue: '',               // preso direttamente dalla user story se non presente
            description: 'Repository del codice consegnato. Vuoto: quello scritto nella user story, poi projects.json'
        )
        string(
            name: 'CONTRACT',
            defaultValue: '0xBd5fdFc6A7Dd88ee35824cb4567420EB0177b50b',   //per prova
            description: 'Smart contract delle user story su Sepolia'
        )
        booleanParam(
            name: 'WRITE_BACK',
            defaultValue: true,             // falso = prova a vuoto, non scrive sulla task
            description: 'Scrive il resoconto e cambia lo stato nel sistema di project management'
        )
        booleanParam(
            name: 'SIGN_CHAIN',
            defaultValue: true,             // falso = prova a vuoto, non spende gas
            description: 'Firma sulla blockchain se tutti i criteri automatici passano'
        )
    }

    environment {                           // variabili d'ambiente
        SYSTEM           = "${params.SYSTEM}"       // Groovy
        TASK             = "${params.TASK}"         
        REPOSITORY       = "${params.REPOSITORY}"
        CONTRACT_ADDRESS = "${params.CONTRACT}"

        OP_URL       = 'http://127.0.0.1:8090'      // OpenProject locale mio
        TAIGA_URL    = 'https://api.taiga.io'
        TAIGA_SLUG   = 'simomnz-prova-api'
        JIRA_URL     = 'https://simomnz.atlassian.net'
        JIRA_PROJECT = 'KAN'                        // per non dover scrivere sempre "KAN-"
        SEPOLIA_RPC  = 'https://ethereum-sepolia-rpc.publicnode.com'     //blockchain

        VENV = '/var/lib/jenkins/venv-verifica'     // fuori dallo spazio di lavoro
    }                                               

    stages {

        stage('1. Verificatore') {
            steps {
                echo '--- Codice del sistema di verifica ---'
                git branch: 'main', url: 'https://github.com/simomnz/Tirocinio.git'   // git clone del codice VERIFICATORE
        }
        }
        // CODICE UNIX
        stage('2. Dipendenze') {
            steps {
                echo '--- behave e web3, nelle versioni fissate ---'
                sh '''
                    if [ ! -d "$VENV" ]; then       # -d per cartella, ! se non esiste
                        python3 -m venv "$VENV"     # creato una volta sola
                    fi
                    . "$VENV/bin/activate"          # . e' source

                    pip install --quiet -r vocabolario/requirements.txt   # -r elenco da file, --quiet solo errori, solo se non e' tutto installato 
                    echo "Ambiente pronto:"
                    pip list --format=freeze | grep -E '^(behave|web3)='  # -E = regex estesa, ^ = inizio riga   # stampa le versioni
                '''                                 
            }                                       // virgolette SINGOLE: nessuna sostituzione, $VENV lo risolve la shell
        }

        stage('3. Verifica') {
            steps {
                script {                            // Groovy

                    def repository = params.REPOSITORY?.trim()   // ? se nulllo non da errore, .trim() cancella gli spazi

                    echo "--- Criteri da ${params.SYSTEM} ${params.TASK} ---"
                    if (repository) {
                        echo "--- Codice da ${repository} ---"
                    } else {
                        echo '--- Codice dal repository scritto nella user story ---'
                    }

                    withCredentials([               // Le Credenziali NON VISIBILI
                        string(credentialsId: 'op-token',     variable: 'OP_TOKEN'),     
                        string(credentialsId: 'taiga-user',   variable: 'TAIGA_USER'),
                        string(credentialsId: 'taiga-pass',   variable: 'TAIGA_PASS'),
                        string(credentialsId: 'jira-user',    variable: 'JIRA_USER'),
                        string(credentialsId: 'jira-token',   variable: 'JIRA_TOKEN'),
                        string(credentialsId: 'verifier-key', variable: 'VERIFIER_KEY')
                    ]) {                            // nascosti nei log ******

                        def flags = ''
                        if (params.WRITE_BACK) { flags += ' --write' }   
                        if (params.SIGN_CHAIN) { flags += ' --chain' }
                        //UNIX CODE
                        sh """
                            set +x                  # set +x NON stampa i comandi 
                            . "\$VENV/bin/activate"  # \$ per farlo risolvere alla shell e non a Groovy
                            cd vocabolario          

                            set -- "\$SYSTEM" "\$TASK"          # set -- riscrive gli argomenti
                            if [ -n "\$REPOSITORY" ]; then      # -n la stringa NON e' vuota
                                set -- "\$@" "\$REPOSITORY"      # "\$@"  tutti gli argomenti
                            fi

                            python3 verify.py "\$@"${flags}     # OUTPUT: 0 passa, 1 no, 2 non ha potuto provare
                        """                                     // diverso da zero, sh fallisce e la build fallisce
                    }
                }
            }
        }
    }

    post {                                          // Dopo tutti gli stage
        success {
            echo "I criteri di accettazione di ${params.TASK} sono soddisfatti."
        }
        failure {
            echo "La consegna non soddisfa i criteri di ${params.TASK}: il resoconto e' nel log e nel commento sulla task."
        }
    }
}