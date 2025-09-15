import React from "react";
import {
  Avatar,
  Menu,
  MenuTrigger,
  MenuPopover,
  MenuList,
  MenuItem,
  Button,
  Tooltip,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import { SignOut24Regular } from "@fluentui/react-icons";
import useAuth from "../../msal-auth/useAuth";

const useStyles = makeStyles({
  userButton: {
    minWidth: "auto",
    paddingLeft: tokens.spacingHorizontalXS,
    paddingRight: tokens.spacingHorizontalXS,
  },
  menuItem: {
    paddingLeft: tokens.spacingHorizontalM,
    paddingRight: tokens.spacingHorizontalM,
  },
  userInfo: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: tokens.spacingVerticalXXS,
  },
  userName: {
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase200,
  },
  userEmail: {
    fontSize: tokens.fontSizeBase100,
    color: tokens.colorNeutralForeground2,
  },
});

const UserMenu: React.FC = () => {
  const styles = useStyles();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
  };

  // Get user initials for avatar
  const getUserInitials = (name: string | undefined): string => {
    if (!name) return "U";
    
    // Remove anything in parentheses first
    const cleanName = name.replace(/\s*\([^)]*\)/g, '').trim();
    const parts = cleanName.split(" ");
    
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return cleanName.charAt(0).toUpperCase();
  };

  const userDisplayName = user?.name || user?.shortName || "User";
  const userEmail = user?.username || "";

  return (
    <Menu>
      <MenuTrigger disableButtonEnhancement>
        <Tooltip content={`Signed in as ${userDisplayName}`} relationship="label">
          <Button
            appearance="subtle"
            className={styles.userButton}
            icon={
              <Avatar
                name={userDisplayName}
                initials={getUserInitials(userDisplayName)}
                size={28}
                color="colorful"
                style={{ fontWeight: "bold" }}
              />
            }
          />
        </Tooltip>
      </MenuTrigger>

      <MenuPopover>
        <MenuList>
          <MenuItem className={styles.menuItem} disabled>
            <div className={styles.userInfo}>
              <div className={styles.userName}>{userDisplayName}</div>
              {userEmail && <div className={styles.userEmail}>{userEmail}</div>}
            </div>
          </MenuItem>
          <MenuItem
            className={styles.menuItem}
            icon={<SignOut24Regular />}
            onClick={handleLogout}
          >
            Sign out
          </MenuItem>
        </MenuList>
      </MenuPopover>
    </Menu>
  );
};

export default UserMenu;
