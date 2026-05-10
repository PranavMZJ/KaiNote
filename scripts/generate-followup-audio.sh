#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Generate follow-up meeting audio files using Amazon Polly
# Creates two follow-up meetings for the Product Launch series
# ---------------------------------------------------------------------------

set -euo pipefail

AWS_PROFILE="terraform"
AWS_REGION="ap-northeast-1"
OUTPUT_DIR="docs/Testing/product-launch-series"

mkdir -p "$OUTPUT_DIR"

echo "=============================================="
echo "  Generating Follow-Up Meeting Audio Files"
echo "=============================================="
echo ""

# =============================================
# Meeting 2: Friday Go/No-Go Decision
# (Follow-up to the Product Launch Review)
# Speakers: Sarah (lead), David (eng), Lisa (legal/marketing)
# =============================================

echo "==> Meeting 2: Friday Go/No-Go Decision..."

# Speaker 1 - Sarah (meeting lead) - uses Joanna
SARAH_TEXT_1="Good morning everyone. This is our Friday go no-go meeting for the product launch. Let's go through each item from Monday's review. David, how are the critical bugs?"

# Speaker 2 - David (engineering) - uses Matthew
DAVID_TEXT_1="Good news. Both critical bugs are fixed and deployed to staging. We're down to 8 open bugs total, all low priority. The staging migration ran successfully on Wednesday with zero data loss. I also set up the rollback plan. We have automated scripts that can revert the database and redeploy the previous version within 15 minutes."

# Speaker 3 - Lisa (legal/marketing) - uses Ruth
LISA_TEXT_1="Great work David. On the legal front, we got approval on the updated terms of service yesterday. So we're clear to use the new terms at launch. Marketing is also ready. The landing page went live on Monday as planned, and we've already got 200 early sign-ups from the waitlist."

# Speaker 1 - Sarah
SARAH_TEXT_2="Excellent. So let me summarize. Engineering is green, all critical bugs fixed, rollback plan in place. Legal is green, terms approved. Marketing is green, landing page live. The only remaining item is the production database migration, which David will run the night before launch. Are there any new risks or concerns?"

# Speaker 2 - David
DAVID_TEXT_2="One thing I want to flag. During load testing yesterday, we noticed the response time increases slightly when we hit 4500 concurrent users. It's still within acceptable limits, but I'd like to add an auto-scaling rule as a safety net. I can have that done by end of day."

# Speaker 3 - Lisa
LISA_TEXT_2="That sounds reasonable. From marketing's side, we're expecting about 2000 users in the first hour based on our email list size. So we should have plenty of headroom. I'll also have the support team on standby for launch day."

# Speaker 1 - Sarah
SARAH_TEXT_3="Perfect. Based on everything we've discussed, I'm calling this a go. Launch date is confirmed for next Wednesday. David, please add the auto-scaling rule today and run the production migration Tuesday night. Lisa, please send the launch day email campaign schedule to the team by Monday. Let's reconvene Tuesday afternoon for a final pre-launch check. Great work everyone."

# Generate individual segments
aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$SARAH_TEXT_1" --output-format mp3 --engine neural --voice-id Joanna \
  "$OUTPUT_DIR/m2_seg1.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$DAVID_TEXT_1" --output-format mp3 --engine neural --voice-id Matthew \
  "$OUTPUT_DIR/m2_seg2.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$LISA_TEXT_1" --output-format mp3 --engine neural --voice-id Ruth \
  "$OUTPUT_DIR/m2_seg3.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$SARAH_TEXT_2" --output-format mp3 --engine neural --voice-id Joanna \
  "$OUTPUT_DIR/m2_seg4.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$DAVID_TEXT_2" --output-format mp3 --engine neural --voice-id Matthew \
  "$OUTPUT_DIR/m2_seg5.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$LISA_TEXT_2" --output-format mp3 --engine neural --voice-id Ruth \
  "$OUTPUT_DIR/m2_seg6.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$SARAH_TEXT_3" --output-format mp3 --engine neural --voice-id Joanna \
  "$OUTPUT_DIR/m2_seg7.mp3" > /dev/null

# Generate 2 seconds of silence for gaps
# Using Polly to generate a silent SSML break instead of ffmpeg
aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --engine neural --text-type ssml \
  --text '<speak><break time="2s"/></speak>' \
  --output-format mp3 --voice-id Joanna \
  "$OUTPUT_DIR/silence.mp3" > /dev/null

# Concatenate with silence gaps (MP3 is a streaming format, cat works)
echo "    Concatenating segments..."
cat "$OUTPUT_DIR/m2_seg1.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m2_seg2.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m2_seg3.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m2_seg4.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m2_seg5.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m2_seg6.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m2_seg7.mp3" \
    > "$OUTPUT_DIR/meeting-2-go-no-go-decision.mp3"

echo "    ✓ Meeting 2 generated: $OUTPUT_DIR/meeting-2-go-no-go-decision.mp3"
echo ""

# =============================================
# Meeting 3: Post-Launch Debrief (1 week after launch)
# Speakers: Sarah (lead), David (eng), Lisa (marketing)
# =============================================

echo "==> Meeting 3: Post-Launch Debrief..."

# Speaker 1 - Sarah
SARAH_TEXT_P1="Welcome everyone to our post-launch debrief. It's been one week since we launched, and I want to review how things went. David, let's start with the technical side."

# Speaker 2 - David
DAVID_TEXT_P1="Overall the launch went smoothly. The production migration ran without issues Tuesday night. We hit a peak of 3200 concurrent users on launch day, well within our capacity. The auto-scaling rule I added kicked in once during a traffic spike on Thursday, which validated that decision. We did have one incident. There was a 12-minute outage on Thursday afternoon caused by a connection pool exhaustion issue. I've already deployed a fix that increases the pool size and adds better connection recycling."

# Speaker 3 - Lisa
LISA_TEXT_P1="From the marketing side, the numbers are strong. We have 4500 registered users after one week, which is 125% of our target. The email campaign had a 32% open rate and 8% click-through rate, both above industry average. Customer feedback has been mostly positive. The main complaint is about the onboarding flow being confusing. I've logged that as a product improvement for next sprint."

# Speaker 1 - Sarah
SARAH_TEXT_P2="Those are great numbers Lisa. David, regarding the Thursday outage, do we need to worry about that happening again? And what about the remaining low-priority bugs from before launch?"

# Speaker 2 - David
DAVID_TEXT_P2="The connection pool fix is solid. I've also added monitoring alerts so we'll know before it becomes an issue again. For the remaining bugs, we've fixed 5 of the 8 low-priority ones this week. The other 3 are cosmetic issues that I'll address in the next sprint. One new thing I want to raise. We're seeing higher than expected storage costs on S3 because users are uploading larger files than we anticipated. I think we should implement file size limits or move to a tiered storage approach."

# Speaker 3 - Lisa
LISA_TEXT_P2="I agree with David on the storage issue. From a product perspective, we should also consider the onboarding improvements. I'd like to propose a quick design sprint next week to address both the onboarding flow and the file upload experience. I can coordinate with the design team."

# Speaker 1 - Sarah
SARAH_TEXT_P3="Good suggestions. Let me summarize the action items. David, please write up a proposal for the storage optimization by next Wednesday. Include cost projections and recommended file size limits. Lisa, please schedule the design sprint for next week and invite the relevant stakeholders. I'll update the executive team on our launch metrics and the post-launch roadmap. Let's also keep monitoring the system closely for another week before we reduce the on-call rotation. Great launch everyone. Well done."

# Generate individual segments
aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$SARAH_TEXT_P1" --output-format mp3 --engine neural --voice-id Joanna \
  "$OUTPUT_DIR/m3_seg1.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$DAVID_TEXT_P1" --output-format mp3 --engine neural --voice-id Matthew \
  "$OUTPUT_DIR/m3_seg2.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$LISA_TEXT_P1" --output-format mp3 --engine neural --voice-id Ruth \
  "$OUTPUT_DIR/m3_seg3.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$SARAH_TEXT_P2" --output-format mp3 --engine neural --voice-id Joanna \
  "$OUTPUT_DIR/m3_seg4.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$DAVID_TEXT_P2" --output-format mp3 --engine neural --voice-id Matthew \
  "$OUTPUT_DIR/m3_seg5.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$LISA_TEXT_P2" --output-format mp3 --engine neural --voice-id Ruth \
  "$OUTPUT_DIR/m3_seg6.mp3" > /dev/null

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --text "$SARAH_TEXT_P3" --output-format mp3 --engine neural --voice-id Joanna \
  "$OUTPUT_DIR/m3_seg7.mp3" > /dev/null

# Concatenate with silence gaps
echo "    Concatenating segments..."
cat "$OUTPUT_DIR/m3_seg1.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m3_seg2.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m3_seg3.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m3_seg4.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m3_seg5.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m3_seg6.mp3" "$OUTPUT_DIR/silence.mp3" \
    "$OUTPUT_DIR/m3_seg7.mp3" \
    > "$OUTPUT_DIR/meeting-3-post-launch-debrief.mp3"

echo "    ✓ Meeting 3 generated: $OUTPUT_DIR/meeting-3-post-launch-debrief.mp3"
echo ""

# =============================================
# Copy original meeting into the series folder
# =============================================

echo "==> Copying original meeting into series folder..."
cp "docs/Testing/test-product-launch-meeting.mp3" "$OUTPUT_DIR/meeting-1-product-launch-review.mp3"
echo "    ✓ Copied: $OUTPUT_DIR/meeting-1-product-launch-review.mp3"
echo ""

# =============================================
# Cleanup temp files
# =============================================

echo "==> Cleaning up temporary files..."
rm -f "$OUTPUT_DIR"/m2_seg*.mp3 "$OUTPUT_DIR"/m3_seg*.mp3
rm -f "$OUTPUT_DIR"/silence.mp3
echo "    ✓ Cleanup complete"
echo ""

echo "=============================================="
echo "  Product Launch Meeting Series"
echo "=============================================="
echo ""
echo "  $OUTPUT_DIR/"
echo "  ├── meeting-1-product-launch-review.mp3     (original)"
echo "  ├── meeting-2-go-no-go-decision.mp3         (follow-up 1)"
echo "  └── meeting-3-post-launch-debrief.mp3       (follow-up 2)"
echo ""
echo "  Testing order:"
echo "  1. Play meeting-1 → generates report with action items"
echo "  2. Play meeting-2 → RAG detects prior items, agent checks overdue"
echo "  3. Play meeting-3 → RAG has 2 prior meetings, rich context"
echo ""
