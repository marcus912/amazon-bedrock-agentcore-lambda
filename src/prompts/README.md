# AI Agent Prompts

This directory contains prompt templates for Bedrock AI agents.

## Files

- `github_issue.txt` - Prompt for creating GitHub issues from support/QA team bug report emails

## How It Works

**Default Behavior**: Lambda loads prompts from local filesystem (`src/prompts/github_issue.txt`)

**S3 Override** (Optional): Upload custom prompts to S3 to override local version

### Update Prompts in S3 (Optional)

Upload all prompts to S3:

```bash
bin/update-prompts.sh
```

Upload a specific prompt:

```bash
bin/update-prompts.sh github_issue.txt
```

### S3 Location

Prompts are stored in:
```
s3://${STORAGE_BUCKET_NAME}/prompts/
```
(The bucket name is configured via the `PROMPT_BUCKET` environment variable)

### Prompt Variables

The `github_issue.txt` template uses these variables:

- `{from_address}` - Support/QA team member email address
- `{subject}` - Email subject line
- `{body}` - Email body content
- `{timestamp}` - Email received timestamp

### Loading Strategy

Lambda loads prompts with the following priority:

1. **Cache** (if not expired) → Fast! ⚡
2. **S3 Override** (if `PROMPT_BUCKET` set) → Runtime updates without redeploy
3. **Local Filesystem** → `src/prompts/github_issue.txt` (always available)

**Update Methods**:

**Method 1: Redeploy** (updates local filesystem version)
```bash
# Edit prompt
vim src/prompts/github_issue.txt

# Deploy
bin/deploy.sh
```

**Method 2: S3 Override** (no redeploy needed!)
```bash
# Edit prompt
vim src/prompts/github_issue.txt

# Upload to S3
bin/update-prompts.sh

# Lambda picks up changes within 5 minutes (cache TTL)
```

**Fallback Behavior**:
- ✅ If S3 unavailable → Uses local filesystem version
- ✅ If prompt not in S3 → Uses local filesystem version
- ✅ If `PROMPT_BUCKET` not set → Uses local filesystem version
- ✅ Lambda always works!

### Caching

Prompts are cached in Lambda memory with **TTL (Time-To-Live)**:

**Cache Behavior**:
- **First invocation**: Loads from S3 (or filesystem if S3 unavailable)
- **Warm invocations (within TTL)**: Uses cached version (fast!)
- **After TTL expires**: Automatically reloads from S3
- **Cold start**: Cache empty, loads fresh

**Default TTL**: 5 minutes (300 seconds)

**What this means**:
- ✅ **S3 updates reflected within 5 minutes** on warm containers
- ✅ **Fast performance** - No S3 calls during TTL window
- ✅ **Configurable** - Set `PROMPT_CACHE_TTL` environment variable

**Example Timeline**:
```
00:00 - Load prompt from S3, cache for 5 min
00:01 - Use cache (age: 1 min < 5 min TTL) ⚡
00:03 - Use cache (age: 3 min < 5 min TTL) ⚡
00:06 - Cache expired! Reload from S3 🔄
00:07 - Use cache (age: 1 min < 5 min TTL) ⚡
```

**Configure TTL** (in `template.yaml`):
```yaml
Environment:
  Variables:
    PROMPT_CACHE_TTL: "60"   # 1 minute (faster S3 updates)
    # PROMPT_CACHE_TTL: "300"  # 5 minutes (default, balanced)
    # PROMPT_CACHE_TTL: "600"  # 10 minutes (fewer S3 calls)
```

### View Prompts in S3

```bash
# List all prompts
aws s3 ls s3://${BUCKET_NAME}/prompts/

# Download a prompt
aws s3 cp s3://${BUCKET_NAME}/prompts/github_issue.txt -

# View prompt versions (if versioning enabled)
aws s3api list-object-versions \
  --bucket ${BUCKET_NAME} \
  --prefix prompts/github_issue.txt
```

### Enable S3 Versioning (Optional)

To keep history of prompt changes:

```bash
aws s3api put-bucket-versioning \
  --bucket ${BUCKET_NAME} \
  --versioning-configuration Status=Enabled
```

## Tips

- **Test locally** before uploading to S3
- **Keep prompts concise** - Large prompts increase cost and latency
- **Use clear variable names** - Makes formatting easier
- **Document changes** - Add comments explaining why you changed a prompt
