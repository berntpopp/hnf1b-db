#!/bin/bash
# docker/setup.sh - Automated VPS deployment for HNF1B Database

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  HNF1B Database Setup Script${NC}"
echo -e "${GREEN}=====================================${NC}"

# Check prerequisites
command -v docker &> /dev/null || { echo -e "${RED}Error: Docker not installed${NC}"; exit 1; }
docker compose version &> /dev/null || { echo -e "${RED}Error: Docker Compose V2 not installed${NC}"; exit 1; }

# Check/create docker/.env.docker
if [ ! -f "docker/.env.docker" ]; then
    if [ -f "docker/.env.example" ]; then
        cp docker/.env.example docker/.env.docker
        echo -e "${YELLOW}Created docker/.env.docker - please configure it${NC}"
        echo -e "${YELLOW}Required: POSTGRES_PASSWORD, JWT_SECRET, ADMIN_PASSWORD${NC}"
        exit 1
    else
        echo -e "${RED}Error: docker/.env.example not found${NC}"
        exit 1
    fi
fi

# Validate required variables
source docker/.env.docker
[ -z "$JWT_SECRET" ] || [ "$JWT_SECRET" = "CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_HEX_32" ] && {
    echo -e "${RED}Error: Configure JWT_SECRET (openssl rand -hex 32)${NC}"; exit 1;
}
[ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "CHANGE_ME_TO_SECURE_PASSWORD" ] && {
    echo -e "${RED}Error: Configure POSTGRES_PASSWORD${NC}"; exit 1;
}

# Check/create NPM network
NPM_NETWORK="${NPM_SHARED_NETWORK_NAME:-npm_default}"
docker network ls | grep -q "$NPM_NETWORK" || {
    echo -e "${YELLOW}Creating NPM network '$NPM_NETWORK'...${NC}"
    docker network create "$NPM_NETWORK"
}

# Create symlink in root for convenience
ln -sf docker/.env.docker .env

# Build and start
echo -e "${GREEN}Building Docker images...${NC}"
docker compose -f docker/docker-compose.npm.yml --env-file docker/.env.docker build

echo -e "${GREEN}Starting services...${NC}"
docker compose -f docker/docker-compose.npm.yml --env-file docker/.env.docker up -d

echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 30

docker compose -f docker/docker-compose.npm.yml --env-file docker/.env.docker ps

# Run migrations
echo -e "${GREEN}Running database migrations...${NC}"
docker compose -f docker/docker-compose.npm.yml --env-file docker/.env.docker exec -T hnf1b_api alembic upgrade head

# Check if initial import needed
if [ "$ENABLE_DATA_IMPORT" = "true" ]; then
    echo -e "${GREEN}Running initial data import...${NC}"
    docker compose -f docker/docker-compose.npm.yml --env-file docker/.env.docker exec -T hnf1b_api python -m migration.direct_sheets_to_phenopackets

    echo -e "${YELLOW}Disabling future auto-imports...${NC}"
    # Update the file in docker/ directory
    sed -i 's/ENABLE_DATA_IMPORT=true/ENABLE_DATA_IMPORT=false/' docker/.env.docker
fi

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "1. Configure NPM proxy hosts for hnf1b.org and api.hnf1b.org"
echo -e "2. Point DNS to your VPS IP"
echo -e "3. Request SSL certificates via NPM"
echo ""
echo -e "Commands:"
echo -e "  make docker-logs     # View logs"
echo -e "  make docker-health   # Check health"
echo -e "  make docker-db-backup # Backup database"