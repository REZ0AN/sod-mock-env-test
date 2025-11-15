#!/bin/bash

# send_email.sh - Send audit reports via email

set -e

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[EMAIL]${NC} $1"
}

log_error() {
    echo -e "${RED}[EMAIL ERROR]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[EMAIL WARNING]${NC} $1"
}

# Function to send email with all CSV attachments
send_audit_emails() {
    local RECIPIENTS_FILE="${1:-./email_recipients.txt}"
    local AUDIT_DIR="${2:-./audits}"
    local SUBJECT_PREFIX="${3:-GitHub Audit Report}"
    
    log_info "Starting email distribution..."
    
    # Check if recipients file exists
    if [ ! -f "$RECIPIENTS_FILE" ]; then
        log_error "Recipients file not found: $RECIPIENTS_FILE"
        return 1
    fi
    
    # Check if audit directory exists
    if [ ! -d "$AUDIT_DIR" ]; then
        log_error "Audit directory not found: $AUDIT_DIR"
        return 1
    fi
    
    # Find all CSV files
    AUDIT_FILES=$(find "$AUDIT_DIR" -name "*.csv" -type f)
    
    if [ -z "$AUDIT_FILES" ]; then
        log_warning "No CSV files found in $AUDIT_DIR"
        return 1
    fi
    
    # Count files
    FILE_COUNT=$(echo "$AUDIT_FILES" | wc -l)
    log_info "Found $FILE_COUNT audit file(s)"
    
    # Calculate total size
    TOTAL_SIZE=$(du -ch $AUDIT_FILES 2>/dev/null | tail -1 | cut -f1)
    
    # Read recipients (skip empty lines and comments)
    RECIPIENTS=$(grep -v '^#' "$RECIPIENTS_FILE" | grep -v '^[[:space:]]*$' | tr '\n' ',' | sed 's/,$//')
    
    if [ -z "$RECIPIENTS" ]; then
        log_error "No valid recipients found in $RECIPIENTS_FILE"
        return 1
    fi
    
    log_info "Recipients: $RECIPIENTS"
    
    # Build email subject
    PERIOD_INFO=$(basename "$AUDIT_FILES" | head -1 | sed 's/.*-\([0-9]\{4\}-[0-9]\{2\}\)-to-\([0-9]\{4\}-[0-9]\{2\}\).*/\1 to \2/')
    SUBJECT="$SUBJECT_PREFIX - $PERIOD_INFO"
    
    # Create email body
    BODY_FILE=$(mktemp)
    cat > "$BODY_FILE" << EOF
GitHub Audit Report

Generated: $(date '+%Y-%m-%d %H:%M:%S')
Period: $PERIOD_INFO
Total Reports: $FILE_COUNT
Total Size: $TOTAL_SIZE

Audit Files:
EOF
    
    # Add file details to body
    for file in $AUDIT_FILES; do
        filename=$(basename "$file")
        filesize=$(du -h "$file" | cut -f1)
        echo "  - $filename ($filesize)" >> "$BODY_FILE"
    done
    
    cat >> "$BODY_FILE" << EOF

Summary:
This email contains all audit reports generated for the specified period.
Each CSV file contains commit information for different teams.

Please review the attached reports and contact the development team if you have any questions.

Best regards,
GitHub Audit System
EOF
    
    log_info "Preparing to send email..."
    log_info "Subject: $SUBJECT"
    
    # Build attachment arguments
    ATTACH_ARGS=""
    for file in $AUDIT_FILES; do
        ATTACH_ARGS="$ATTACH_ARGS -A $file"
        log_info "Attaching: $(basename $file)"
    done
    
    # Send email to all recipients
    log_info "Sending email to recipients..."
    
    if cat "$BODY_FILE" | mail -s "$SUBJECT" $ATTACH_ARGS "$RECIPIENTS"; then
        log_info "✓ Email sent successfully to: $RECIPIENTS"
        rm -f "$BODY_FILE"
        return 0
    else
        log_error "Failed to send email"
        rm -f "$BODY_FILE"
        return 1
    fi
}

# Function to send individual emails to each recipient
send_individual_emails() {
    local RECIPIENTS_FILE="${1:-./email_recipients.txt}"
    local AUDIT_DIR="${2:-./audits}"
    local SUBJECT_PREFIX="${3:-GitHub Audit Report}"
    
    log_info "Starting individual email distribution..."
    
    # Check files exist
    if [ ! -f "$RECIPIENTS_FILE" ]; then
        log_error "Recipients file not found: $RECIPIENTS_FILE"
        return 1
    fi
    
    # Find CSV files
    AUDIT_FILES=$(find "$AUDIT_DIR" -name "*.csv" -type f)
    
    if [ -z "$AUDIT_FILES" ]; then
        log_warning "No CSV files found in $AUDIT_DIR"
        return 1
    fi
    
    FILE_COUNT=$(echo "$AUDIT_FILES" | wc -l)
    log_info "Found $FILE_COUNT audit file(s)"
    
    # Build attachment arguments
    ATTACH_ARGS=""
    for file in $AUDIT_FILES; do
        ATTACH_ARGS="$ATTACH_ARGS -A $file"
    done
    
    # Get period info
    PERIOD_INFO=$(basename "$AUDIT_FILES" | head -1 | sed 's/.*-\([0-9]\{4\}-[0-9]\{2\}\)-to-\([0-9]\{4\}-[0-9]\{2\}\).*/\1 to \2/')
    SUBJECT="$SUBJECT_PREFIX - $PERIOD_INFO"
    
    # Create email body
    BODY_FILE=$(mktemp)
    cat > "$BODY_FILE" << EOF
GitHub Audit Report

Generated: $(date '+%Y-%m-%d %H:%M:%S')
Period: $PERIOD_INFO
Total Reports: $FILE_COUNT

This email contains all audit reports for the specified period.

Best regards,
GitHub Audit System
EOF
    
    # Read recipients and send individually
    SUCCESS_COUNT=0
    FAIL_COUNT=0
    
    while IFS= read -r recipient; do
        # Skip empty lines and comments
        [[ -z "$recipient" || "$recipient" =~ ^[[:space:]]*# ]] && continue
        
        # Trim whitespace
        recipient=$(echo "$recipient" | xargs)
        
        log_info "Sending to: $recipient"
        
        if cat "$BODY_FILE" | mail -s "$SUBJECT" $ATTACH_ARGS "$recipient"; then
            log_info "✓ Sent to $recipient"
            ((SUCCESS_COUNT++))
        else
            log_error "✗ Failed to send to $recipient"
            ((FAIL_COUNT++))
        fi
        
        # Small delay between emails
        sleep 1
        
    done < "$RECIPIENTS_FILE"
    
    rm -f "$BODY_FILE"
    
    log_info "Email distribution complete"
    log_info "Successful: $SUCCESS_COUNT"
    log_info "Failed: $FAIL_COUNT"
    
    [ $FAIL_COUNT -eq 0 ] && return 0 || return 1
}

# Main function
main() {
    # Get configuration from environment or use defaults
    RECIPIENTS_FILE="${EMAIL_RECIPIENTS_FILE:-./email_recipients.txt}"
    AUDIT_DIR="${AUDIT_DIR:-./audits}"
    SUBJECT_PREFIX="${EMAIL_SUBJECT:-GitHub Audit Report}"
    SEND_MODE="${SEND_MODE:-combined}"  # "combined" or "individual"
    
    log_info "Email configuration:"
    log_info "  Recipients file: $RECIPIENTS_FILE"
    log_info "  Audit directory: $AUDIT_DIR"
    log_info "  Subject prefix: $SUBJECT_PREFIX"
    log_info "  Send mode: $SEND_MODE"
    echo ""
    
    if [ "$SEND_MODE" = "individual" ]; then
        send_individual_emails "$RECIPIENTS_FILE" "$AUDIT_DIR" "$SUBJECT_PREFIX"
    else
        send_audit_emails "$RECIPIENTS_FILE" "$AUDIT_DIR" "$SUBJECT_PREFIX"
    fi
}

# Run main if script is executed directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi