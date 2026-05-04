pipeline {
    agent any

    environment {
        OP_CREDENTIALS = credentials('OP_CREDENTIALS')
    }

    stages {
        stage('1. Checkout') {
            steps {
                echo '--- Scaricamento codice da GitHub ---'
                git branch: 'main', url: 'https://github.com/simomnz/Tirocinio.git'
            }
        }

        stage('2. Preparazione') {
            steps {
                echo '--- Pulizia e Installazione dipendenze ---'
                sh 'rm -rf node_modules package-lock.json'
                sh 'npm install --legacy-peer-deps'
            }
        }

        stage('3. Audit & Test') {
            steps {
                echo '--- Compilazione e Esecuzione Test ---'
                sh 'npx hardhat clean'
                sh 'npx hardhat compile'
                sh 'npx hardhat test'
            }
        }

        stage('4. Feedback OpenProject') {
            steps {
                echo '--- Invio esito positivo a OpenProject ---'
                script {
                    def comment = '{"comment": {"format": "markdown", "raw": " **Jenkins CI**: Build e TEST superati con successo. I contratti Skills, Hiring e UserStories sono validati."}}'
                    writeFile file: 'comment.json', text: comment
                    
                    sh "curl -f -X POST -u apikey:${OP_CREDENTIALS_PSW} -H 'Content-Type: application/json' -d @comment.json http://127.0.0.1:8090/api/v3/work_packages/1094/activities"
                }
            }
        }
    }

    post {
        failure {
            echo ' La build o i test sono falliti'
        }
    }
}