CREATE TABLE IF NOT EXISTS "new_users" (
        id INTEGER NOT NULL,
        is_activated_project JSON NOT NULL,
        is_active BOOLEAN NOT NULL,
        is_deactivated BOOLEAN NOT NULL,
        is_deactivated_project JSON NOT NULL,
        is_dir_created BOOLEAN NOT NULL,
        is_opened BOOLEAN NOT NULL,
        is_staff BOOLEAN NOT NULL,
        first_name VARCHAR(20) NOT NULL,
        last_name VARCHAR(40) NOT NULL,
        ldap_gid INTEGER NOT NULL,
        ldap_uid INTEGER NOT NULL,
        mail_is_activated BOOLEAN NOT NULL,
        mail_is_deactivated BOOLEAN NOT NULL,
        mail_is_opensend BOOLEAN NOT NULL,
        mail_is_sshkeyadded BOOLEAN NOT NULL,
        mail_is_sshkeyremoved BOOLEAN NOT NULL,
        mail_name_sshkey JSON NOT NULL,
        mail_project_is_activated JSON NOT NULL,
        mail_project_is_deactivated JSON NOT NULL,
        mail_project_is_opensend JSON NOT NULL,
        mail_project_is_sshkeyadded JSON NOT NULL,
        mail_project_is_sshkeyremoved JSON NOT NULL,
        person_mail VARCHAR(60) NOT NULL,
        person_oib VARCHAR(11) NOT NULL,
        person_uniqueid VARCHAR(128) NOT NULL,
        projects_api JSON NOT NULL,
        sshkeys_api JSON NOT NULL,
        type_create VARCHAR(10) NOT NULL,
        uid_api INTEGER NOT NULL,
        username_api VARCHAR(10) NOT NULL,
        PRIMARY KEY (id)
);

INSERT INTO new_users SELECT
id, first_name, last_name, person_mail, person_uniqueid, type_create,
projects_api, person_oib, uid_api, is_active, is_deactivated,
is_activated_project, is_deactivated_project, is_opened, is_staff,
is_dir_created, mail_is_activated, mail_is_deactivated, mail_is_opensend,
mail_is_sshkeyadded, mail_is_sshkeyremoved, mail_name_sshkey,
mail_project_is_opensend, mail_project_is_sshkeyadded,
mail_project_is_sshkeyremoved, mail_project_is_activated,
mail_project_is_deactivated, sshkeys_api, ldap_username, ldap_uid, ldap_gid
FROM users;

DROP TABLE IF EXISTS users;
ALTER TABLE new_users RENAME TO users;
