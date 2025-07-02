import requests
import json
from typing import Dict, Optional
import streamlit as st


class NavidromeUserManager:
    """Manage Navidrome users and accounts"""

    def __init__(self, navidrome_url: str = "http://192.168.1.39:4533"):
        self.base_url = navidrome_url
        self.api_url = f"{navidrome_url}/api"

    def create_family_user(
        self, username: str, password: str, name: str, email: str = ""
    ) -> bool:
        """Create a new family member account"""
        try:
            # This would typically require admin authentication
            # For now, provide instructions for manual creation
            st.info(
                f"""
            **To create a family account for {name}:**
            
            1. Go to {self.base_url}/app
            2. Login as admin
            3. Go to Settings → Users
            4. Click "Create User"
            5. Fill in:
               - Username: {username}
               - Name: {name}
               - Email: {email}
               - Password: {password}
               - Role: User (not Admin)
            
            **Or use Navidrome API with admin token (advanced)**
            """
            )
            return True
        except Exception as e:
            st.error(f"Error creating user: {str(e)}")
            return False

    def get_user_info(self, username: str) -> Optional[Dict]:
        """Get user information (requires authentication)"""
        # This would require proper API authentication
        pass

    def suggest_family_setup(self):
        """Provide family setup suggestions"""
        st.markdown(
            """
        ### 👨‍👩‍👧‍👦 Family Account Setup Guide
        
        **Recommended Structure:**
        - **Admin Account**: Your main account (full access)
        - **Family Members**: Individual accounts with user role
        
        **Account Examples:**
        - `dad` / `mom` - Parent accounts
        - `kid1` / `kid2` - Children accounts
        - `guest` - Temporary access for visitors
        
        **Benefits:**
        - Individual listening history
        - Personal playlists
        - Separate recommendations
        - Activity tracking per user
        
        **Shared Library:**
        - All users access the same music collection
        - No need to duplicate files
        - Consistent organization across accounts
        """
        )
