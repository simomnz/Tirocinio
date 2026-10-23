// Verifica di una user story.
//
// Prende i criteri di accettazione dal sistema di project managemente e
// il codice consegnato da GitHub, li esegue, riporta l'esito nel sistema
// e scrive sulla blockchain se i test automatici sono passati.


pipeline {
    agent any

    parameters {
        choice(
            name: 'SYSTEM',
            choices: ['openproject', 'taiga', 'jira'],
            description: 'Dove sono scritti i criteri di accettazione'
        )
        string(
            name: 'TASK',
            defaultValue: '1115',
            description: 'Identificativo della task: 1115 per OpenProject, 7 per Taiga, KAN-12 per Jira'
        )
        booleanParam(
            name: 'WRITE_BACK',
            defaultValue: true,
            description: 'Scrive il resoconto e cambia lo stato nel sistema di project management'
        )
        booleanParam(
            name: 'SIGN_CHAIN',
            defaultValue: true,
            description: 'Firma sulla blockchain se tutti i criteri automatici passano'
        )
    }

    environment {
        // I parametri resi espliciti, cosi' sono visibili alla shell
        SYSTEM = "${params.SYSTEM}"
        TASK   = "${params.TASK}"

        // Configurazione non segreta: indirizzi e nomi
        OP_URL      = 'http://127.0.0.1:8090'
        TAIGA_URL   = 'https://api.taiga.io'
        TAIGA_USER  = 'simo.mnz@gmail.com'
        TAIGA_SLUG  = 'simomnz-prova-api'
        JIRA_URL    = 'https://simomnz.atlassian.net'
        JIRA_PROJECT = 'KAN'
        JIRA_USER   = 'simo.mnz@gmail.com'
        SEPOLIA_RPC = 'https://ethereum-sepolia-rpc.publicnode.com'

        CONTRACT_ADDRESS = '0xc43766fBdf1c59B2d88bF674C08967E60eE84d08'
    }

    stages {

        stage('1. Il verificatore') {
            steps {
                echo '--- Codice del sistema di verifica ---'
                git branch: 'main', url: 'https://github.com/simomnz/Tirocinio.git'
            }
        }

        stage('2. Dipendenze') {
            steps {
                echo '--- behave e web3 in un ambiente isolato ---'
                // L'ambiente virtuale vive nello spazio di lavoro: non tocca
                // il Python di sistema e non richiede permessi di amministratore.
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --quiet --upgrade pip
                    pip install --quiet behave web3
                '''
            }
        }

        stage('3. Verifica') {
            steps {
                echo "--- Criteri da ${params.SYSTEM} ${params.TASK} ---"

                // I segreti escono dall'archivio di Jenkins solo per la durata
                // di questo comando, e vengono oscurati nei log.
                withCredentials([
                    string(credentialsId: 'op-token',     variable: 'OP_TOKEN'),
                    string(credentialsId: 'taiga-pass',   variable: 'TAIGA_PASS'),
                    string(credentialsId: 'jira-token',   variable: 'JIRA_TOKEN'),
                    string(credentialsId: 'verifier-key', variable: 'VERIFIER_KEY')
                ]) {
                    script {
                        def flags = ''
                        if (params.WRITE_BACK) { flags += ' --write' }
                        if (params.SIGN_CHAIN) { flags += ' --chain' }

                        sh """
                            set +x
                            . .venv/bin/activate
                            cd vocabolario
                            python3 verify.py "\$SYSTEM" "\$TASK"${flags}
                        """
                    }
                }
            }
        }
    }

    post {
        success {
            echo "I criteri di accettazione di ${params.TASK} sono soddisfatti."
        }
        failure {
            echo "La consegna non soddisfa i criteri di ${params.TASK}: il resoconto e' nel log e nel commento sulla task."
        }
    }
}
