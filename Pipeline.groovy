pipeline {
    agent any

    environment {
        // OP_CREDENTIALS_USR (apikey) e OP_CREDENTIALS_PSW (il tuo token)
        OP_CREDENTIALS = credentials('OP_CREDENTIALS')
        // TAIGA_CREDENTIALS_USR (mail) e TAIGA_CREDENTIALS_PSW (password)
        TAIGA_CREDENTIALS = credentials('TAIGA_CREDENTIALS')
        // JIRA_CREDENTIALS_USR (mail) e JIRA_CREDENTIALS_PSW (token)
        JIRA_CREDENTIALS = credentials('JIRA_CREDENTIALS')
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
                echo '--- Pulizia profonda e Installazione dipendenze ---'
                sh 'rm -rf node_modules package-lock.json'
                sh 'npm install --legacy-peer-deps'
            }
        }

        stage('3. Compilazione') {
            steps {
                echo '--- Compilazione dei contratti ---'
                sh 'npx hardhat clean'
                sh 'npx hardhat compile'
            }
        }

        stage('4. Test di accettazione') {
            steps {
                echo '--- Esecuzione dei 26 test di accettazione ---'
                // -k true: senza, remix-tests esce con 0 anche con i test rossi
                // e la build risulterebbe verde. Verificato sul campo.
                sh 'npx remix-tests -k true tests/'
            }
        }

        stage('5. Feedback OpenProject') {
            steps {
                echo '--- Invio esito positivo a OpenProject ---'
                script {
                    def comment = '{"comment": {"format": "markdown", "raw": "✅ **Jenkins CI**: Build e 26 test di accettazione superati. I contratti Skills, Hiring e UserStories sono validati."}}'
                    writeFile file: 'comment.json', text: comment
                }
                sh '''
                    set +x
                    curl -f -X POST -u apikey:$OP_CREDENTIALS_PSW \
                      -H 'Content-Type: application/json' \
                      -d @comment.json \
                      http://127.0.0.1:8090/api/v3/work_packages/1094/activities > /dev/null
                    echo "Commento inviato al work package 1094"
                '''
            }
        }

        stage('6. Feedback Taiga') {
            steps {
                echo '--- Invio esito positivo a Taiga ---'
                // Taiga richiede due chiamate: prima si legge la user story per
                // conoscere la sua "version", poi si invia il commento con quella.
                sh '''
                    set +x
                    DATI=$(jq -n --arg u "$TAIGA_CREDENTIALS_USR" --arg p "$TAIGA_CREDENTIALS_PSW" \
                      '{type:"normal", username:$u, password:$p}')

                    TOKEN=$(curl -sS -X POST -H 'Content-Type: application/json' \
                      -d "$DATI" https://api.taiga.io/api/v1/auth | jq -r '.auth_token')

                    US=$(curl -sS -H "Authorization: Bearer $TOKEN" \
                      "https://api.taiga.io/api/v1/userstories/by_ref?ref=1&project__slug=simomnz-prova-api")

                    US_ID=$(echo "$US" | jq -r '.id')
                    US_VERSION=$(echo "$US" | jq -r '.version')

                    COMMENTO=$(jq -n \
                      --arg c "Jenkins CI build $BUILD_NUMBER: 26 test di accettazione superati." \
                      --argjson v "$US_VERSION" \
                      '{comment:$c, version:$v}')

                    curl -f -sS -X PATCH -H 'Content-Type: application/json' \
                      -H "Authorization: Bearer $TOKEN" \
                      -d "$COMMENTO" \
                      "https://api.taiga.io/api/v1/userstories/$US_ID" > /dev/null

                    echo "Commento inviato alla user story $US_ID (version $US_VERSION)"
                '''
            }
        }

        stage('7. Feedback Jira') {
            steps {
                echo '--- Invio esito positivo a Jira ---'
                // Jira vuole il commento in Atlassian Document Format,
                // non come testo semplice.
                sh '''
                    set +x
                    COMMENTO=$(jq -n \
                      --arg t "Jenkins CI build $BUILD_NUMBER: 26 test di accettazione superati." \
                      '{ body: { type: "doc", version: 1,
                         content: [ { type: "paragraph",
                                      content: [ { type: "text", text: $t } ] } ] } }')

                    curl -f -sS -X POST \
                      -u "$JIRA_CREDENTIALS_USR:$JIRA_CREDENTIALS_PSW" \
                      -H 'Content-Type: application/json' \
                      -d "$COMMENTO" \
                      https://simomnz.atlassian.net/rest/api/3/issue/KAN-1/comment > /dev/null

                    echo "Commento inviato alla issue KAN-1"
                '''
            }
        }
    }

    post {
        failure {
            echo '❌ La build o i test sono falliti. Controlla i log!'
        }
    }
}
