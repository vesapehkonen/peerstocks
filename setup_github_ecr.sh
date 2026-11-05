#!/usr/bin/env bash
set -euo pipefail

# One-time AWS setup for GitHub Actions image publishing. Safe to rerun.
# Usage: AWS_REGION=us-west-2 ./setup_github_ecr.sh
# Override GITHUB_OIDC_SUB if this repository uses GitHub's immutable OIDC
# subject format (which includes owner and repository IDs).

for tool in aws jq; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Required command not found: $tool" >&2
    exit 1
  fi
done

export AWS_PAGER=""
region="${AWS_REGION:-${REGION:-us-west-2}}"
github_repository="${GITHUB_REPOSITORY:-vesapehkonen/peerstocks}"
oidc_subject="${GITHUB_OIDC_SUB:-repo:${github_repository}:ref:refs/heads/main}"
role_name="peerstocks-github-ecr-push"
policy_name="peerstocks-github-ecr-push"
repositories=(peerstocks/ingest peerstocks/backend peerstocks/frontend)

if [[ ! "$github_repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "GITHUB_REPOSITORY must be OWNER/REPO" >&2
  exit 1
fi

identity="$(aws sts get-caller-identity --region "$region" --output json)"
account_id="$(jq -r '.Account' <<<"$identity")"
identity_arn="$(jq -r '.Arn' <<<"$identity")"
partition="${identity_arn#arn:}"
partition="${partition%%:*}"
provider_arn="arn:${partition}:iam::${account_id}:oidc-provider/token.actions.githubusercontent.com"
policy_arn="arn:${partition}:iam::${account_id}:policy/${policy_name}"

echo "AWS account: $account_id; region: $region"
echo "GitHub OIDC subject: $oidc_subject"

for repository in "${repositories[@]}"; do
  if output="$(aws ecr describe-repositories --region "$region" --repository-names "$repository" --output json 2>&1)"; then
    echo "ECR repository exists: $repository"
  elif [[ "$output" == *RepositoryNotFoundException* ]]; then
    aws ecr create-repository --region "$region" --repository-name "$repository" \
      --image-scanning-configuration scanOnPush=true >/dev/null
    echo "Created ECR repository: $repository"
  else
    echo "$output" >&2
    exit 1
  fi
done

if output="$(aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$provider_arn" --output json 2>&1)"; then
  if ! jq -e '.ClientIDList | index("sts.amazonaws.com") != null' <<<"$output" >/dev/null; then
    echo "Existing GitHub OIDC provider lacks the sts.amazonaws.com audience: $provider_arn" >&2
    exit 1
  fi
  echo "GitHub OIDC provider exists: $provider_arn"
elif [[ "$output" == *NoSuchEntity* ]]; then
  aws iam create-open-id-connect-provider \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com >/dev/null
  echo "Created GitHub OIDC provider: $provider_arn"
else
  echo "$output" >&2
  exit 1
fi

trust_document="$(jq -n \
  --arg provider "$provider_arn" \
  --arg subject "$oidc_subject" \
  '{Version:"2012-10-17",Statement:[{Effect:"Allow",Principal:{Federated:$provider},Action:"sts:AssumeRoleWithWebIdentity",Condition:{StringEquals:{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com","token.actions.githubusercontent.com:sub":$subject}}}]}')"

policy_document="$(jq -n \
  --arg partition "$partition" \
  --arg region "$region" \
  --arg account "$account_id" \
  '{Version:"2012-10-17",Statement:[
    {Effect:"Allow",Action:["ecr:GetAuthorizationToken"],Resource:"*"},
    {Effect:"Allow",Action:["ecr:BatchCheckLayerAvailability","ecr:BatchGetImage","ecr:CompleteLayerUpload","ecr:InitiateLayerUpload","ecr:PutImage","ecr:UploadLayerPart"],Resource:( ["ingest","backend","frontend"] | map("arn:\($partition):ecr:\($region):\($account):repository/peerstocks/\(.)") )}
  ]}')"

if output="$(aws iam get-policy --policy-arn "$policy_arn" --output json 2>&1)"; then
  version="$(jq -r '.Policy.DefaultVersionId' <<<"$output")"
  existing="$(aws iam get-policy-version --policy-arn "$policy_arn" --version-id "$version" --output json | jq -S -c '.PolicyVersion.Document')"
  desired="$(jq -S -c '.' <<<"$policy_document")"
  if [[ "$existing" != "$desired" ]]; then
    echo "Existing IAM policy differs from the expected ECR permissions: $policy_arn" >&2
    exit 1
  fi
  echo "IAM push policy exists: $policy_arn"
elif [[ "$output" == *NoSuchEntity* ]]; then
  aws iam create-policy --policy-name "$policy_name" --policy-document "$policy_document" >/dev/null
  echo "Created IAM push policy: $policy_arn"
else
  echo "$output" >&2
  exit 1
fi

if output="$(aws iam get-role --role-name "$role_name" --output json 2>&1)"; then
  existing="$(jq -S -c '.Role.AssumeRolePolicyDocument' <<<"$output")"
  desired="$(jq -S -c '.' <<<"$trust_document")"
  if [[ "$existing" != "$desired" ]]; then
    echo "Existing IAM role has a different OIDC trust policy: $role_name" >&2
    exit 1
  fi
  echo "IAM GitHub role exists: $role_name"
elif [[ "$output" == *NoSuchEntity* ]]; then
  aws iam create-role --role-name "$role_name" \
    --assume-role-policy-document "$trust_document" >/dev/null
  echo "Created IAM GitHub role: $role_name"
else
  echo "$output" >&2
  exit 1
fi

attachments="$(aws iam list-attached-role-policies --role-name "$role_name" --output json)"
if jq -e --arg arn "$policy_arn" 'any(.AttachedPolicies[]; .PolicyArn == $arn)' <<<"$attachments" >/dev/null; then
  echo "Push policy is already attached to the role"
else
  aws iam attach-role-policy --role-name "$role_name" --policy-arn "$policy_arn"
  echo "Attached push policy to the role"
fi

echo "GitHub Actions role ARN: arn:${partition}:iam::${account_id}:role/${role_name}"
