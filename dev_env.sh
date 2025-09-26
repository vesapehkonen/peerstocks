export $(grep -v '^#' ./.env | xargs)
export APP_ENV=development
export OS_HOST=http://localhost:9200
