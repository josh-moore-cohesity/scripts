# **helios_role_permissions.py**

   Capture all Helios privileges and roles that contain the privilege.

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/User%20Management/Role%20Permissions%20Audit/helios_role_permissions.py
   
## **Examples**

### Get Privileges and Roles
    python helios_role_permissions.py

# **audit_helios_privileges.py**

   Capture all Helios privileges and roles that contain the specified privilege.

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/User%20Management/Role%20Permissions%20Audit/audit_helios_privileges.py

## **Parameters**
   At least 1 of -s or -o must be specified.  Both may also be used
* -priv (privilege to query for)
* -showroles (show roles that contain the privilege)
* -showusers (show users that have a role that contains the privilege)
  
## **Examples**

### Get Roles that have a specified privilege
    python audit_helios_privileges.py -priv mcm_unregister -showroles

### Get Users that have a specified privilege
    python audit_helios_privileges.py -priv mcm_unregister -showusers

## Get Users and Roles that have a specified privilege
    python audit_helios_privileges.py -priv mcm_unregister -showusers -showroles
    
