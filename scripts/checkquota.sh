#!/bin/bash
set -e

# ================================================
# Azure Quota Validator for Pipelines (CI/CD Safe)
# Logs in using Service Principal credentials.
# Exports VALID_REGION to $GITHUB_ENV if found.
# Default model capacity: o3:500
# ================================================

# ----- Configuration -----
DEFAULT_MODEL_CAPACITY="o3:500"
DEFAULT_REGIONS="eastus,uksouth,eastus2,northcentralus,swedencentral,westus,westus2,southcentralus,canadacentral"

# ----- Environment Variables -----
AZURE_CLIENT_ID="${AZURE_CLIENT_ID}"
AZURE_TENANT_ID="${AZURE_TENANT_ID}"
AZURE_CLIENT_SECRET="${AZURE_CLIENT_SECRET}"
AZURE_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID}"
REGIONS="${AZURE_REGIONS:-$DEFAULT_REGIONS}"

# ----- Authenticate -----
echo "🔐 Authenticating with Azure using Service Principal..."
if ! az login --service-principal -u "$AZURE_CLIENT_ID" -p "$AZURE_CLIENT_SECRET" --tenant "$AZURE_TENANT_ID" &>/dev/null; then
  echo "❌ ERROR: Azure authentication failed."
  exit 1
fi

# ----- Validate Required Variables -----
if [[ -z "$AZURE_SUBSCRIPTION_ID" || -z "$AZURE_CLIENT_ID" || -z "$AZURE_TENANT_ID" || -z "$AZURE_CLIENT_SECRET" ]]; then
  echo "❌ ERROR: Missing required environment variables."
  exit 1
fi

# ----- Set Subscription -----
echo "🎯 Setting active subscription..."
if ! az account set --subscription "$AZURE_SUBSCRIPTION_ID" &>/dev/null; then
  echo "❌ ERROR: Invalid or inaccessible subscription ID."
  exit 1
fi
echo "✅ Subscription set successfully: $AZURE_SUBSCRIPTION_ID"

# ----- Parse Model-Capacity Pairs -----
IFS=',' read -r -a MODEL_CAPACITY_PAIRS <<< "$DEFAULT_MODEL_CAPACITY"
declare -a FINAL_MODEL_NAMES
declare -a FINAL_CAPACITIES

for PAIR in "${MODEL_CAPACITY_PAIRS[@]}"; do
  MODEL_NAME=$(echo "$PAIR" | cut -d':' -f1 | tr '[:upper:]' '[:lower:]')
  CAPACITY=$(echo "$PAIR" | cut -d':' -f2)

  if [[ -z "$MODEL_NAME" || -z "$CAPACITY" ]]; then
    echo "❌ ERROR: Invalid model-capacity pair '$PAIR'."
    exit 1
  fi

  FINAL_MODEL_NAMES+=("$MODEL_NAME")
  FINAL_CAPACITIES+=("$CAPACITY")
done

# ----- Split Regions -----
IFS=',' read -r -a REGIONS_ARRAY <<< "$REGIONS"

echo "🧩 Models: ${FINAL_MODEL_NAMES[*]} (Capacities: ${FINAL_CAPACITIES[*]})"
echo "🌍 Checking regions: ${REGIONS_ARRAY[*]}"
echo "-----------------------------------------------"

VALID_REGION=""
TABLE_ROWS=()
INDEX=1

# ----- Region Loop -----
for REGION in "${REGIONS_ARRAY[@]}"; do
  echo "🔍 Checking region: $REGION"
  
  QUOTA_INFO=$(az cognitiveservices usage list --location "$REGION" --output json 2>/dev/null | tr '[:upper:]' '[:lower:]')
  if [[ -z "$QUOTA_INFO" ]]; then
    echo "⚠️ WARNING: Unable to fetch quota for $REGION. Skipping."
    continue
  fi

  REGION_VALID=true
  TEMP_ROWS=()

  for i in "${!FINAL_MODEL_NAMES[@]}"; do
    MODEL_NAME="${FINAL_MODEL_NAMES[$i]}"
    REQUIRED_CAPACITY="${FINAL_CAPACITIES[$i]}"
    FOUND=false
    INSUFFICIENT_QUOTA=false

    MODEL_TYPES=("openai.standard.$MODEL_NAME" "openai.globalstandard.$MODEL_NAME")

    for MODEL_TYPE in "${MODEL_TYPES[@]}"; do
      MODEL_INFO=$(echo "$QUOTA_INFO" | awk -v model="\"value\": \"$MODEL_TYPE\"" '
        BEGIN { RS="},"; FS="," }
        $0 ~ model { print $0 }
      ')

      if [[ -z "$MODEL_INFO" ]]; then
        continue
      fi

      FOUND=true
      CURRENT_VALUE=$(echo "$MODEL_INFO" | awk -F': ' '/"currentvalue"/ {print $2}' | tr -d ', ')
      LIMIT=$(echo "$MODEL_INFO" | awk -F': ' '/"limit"/ {print $2}' | tr -d ', ')

      CURRENT_VALUE=${CURRENT_VALUE:-0}
      LIMIT=${LIMIT:-0}
      CURRENT_VALUE=$(echo "$CURRENT_VALUE" | cut -d'.' -f1)
      LIMIT=$(echo "$LIMIT" | cut -d'.' -f1)
      AVAILABLE=$((LIMIT - CURRENT_VALUE))

      printf "   ▪ %s | Used: %s | Limit: %s | Available: %s\n" "$MODEL_TYPE" "$CURRENT_VALUE" "$LIMIT" "$AVAILABLE"

      if (( AVAILABLE < REQUIRED_CAPACITY )); then
        echo "     ❌ Insufficient quota for $MODEL_TYPE in $REGION (required: $REQUIRED_CAPACITY)"
        REGION_VALID=false
        INSUFFICIENT_QUOTA=true
        break
      else
        TEMP_ROWS+=("$(printf "| %-3s | %-15s | %-40s | %-8s | %-8s | %-8s |" "$INDEX" "$REGION" "$MODEL_TYPE" "$LIMIT" "$CURRENT_VALUE" "$AVAILABLE")")
      fi
    done

    if [[ "$INSUFFICIENT_QUOTA" == true ]]; then
      break
    fi
  done

  if [[ "$REGION_VALID" == true ]]; then
    VALID_REGION="$REGION"
    TABLE_ROWS+=("${TEMP_ROWS[@]}")
    echo "✅ Region $REGION has sufficient quota."
    break
  else
    echo "🚫 Region $REGION skipped (insufficient quota)."
  fi

  INDEX=$((INDEX + 1))
done

# ----- Final Results -----
echo "-----------------------------------------------"
if [[ -z "$VALID_REGION" ]]; then
  echo "❌ No region found with sufficient quota."
  echo "QUOTA_FAILED=true" >> "$GITHUB_ENV"
  echo "➡️  To request a quota increase: https://aka.ms/oai/stuquotarequest"
  exit 0
else
  echo "✅ VALID REGION FOUND: $VALID_REGION"
  echo "VALID_REGION=$VALID_REGION" >> "$GITHUB_ENV"

  echo "-----------------------------------------------------------"
  printf "| %-3s | %-15s | %-40s | %-8s | %-8s | %-8s |\n" "No." "Region" "Model Name" "Limit" "Used" "Avail"
  echo "-----------------------------------------------------------"
  for ROW in "${TABLE_ROWS[@]}"; do
    echo "$ROW"
  done
  echo "-----------------------------------------------------------"
  exit 0
fi
