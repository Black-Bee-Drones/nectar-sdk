#!/bin/bash

cmd_git_ssh() {
    log_section "CONFIGURING GIT & SSH"

    if git config --global user.name &> /dev/null; then
        log_info "Git configured: $(git config --global user.name) <$(git config --global user.email)>"
        read -p "Reconfigure? (y/N): " -n 1 -r && echo
        [[ ! $REPLY =~ ^[Yy]$ ]] && return
    fi

    read -p "Git name: " git_name
    read -p "Git email: " git_email
    git config --global user.name "$git_name"
    git config --global user.email "$git_email"

    if [ ! -f ~/.ssh/id_ed25519 ]; then
        log_info "Generating SSH key..."
        ssh-keygen -t ed25519 -C "$git_email" -f ~/.ssh/id_ed25519 -N ""
        eval "$(ssh-agent -s)" && ssh-add ~/.ssh/id_ed25519
        echo ""
        log_warning "Add this key to GitHub: https://github.com/settings/keys"
        cat ~/.ssh/id_ed25519.pub
        read -p "Press Enter after adding key to GitHub..."
    fi
    log_success "Git & SSH configured"
}
