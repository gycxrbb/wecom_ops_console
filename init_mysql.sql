CREATE DATABASE IF NOT EXISTS wecom_ops CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE wecom_ops;

CREATE TABLE `groups` (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(128) NOT NULL, 
	alias VARCHAR(128) NOT NULL, 
	group_type VARCHAR(32) NOT NULL, 
	tags TEXT NOT NULL, 
	webhook_cipher TEXT NOT NULL, 
	webhook_mask VARCHAR(128) NOT NULL, 
	enabled INTEGER NOT NULL, 
	default_template_set_id INTEGER, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(64) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	display_name VARCHAR(64) NOT NULL, 
	`role` VARCHAR(32) NOT NULL, 
	status INTEGER NOT NULL, 
	last_login_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE approval_requests (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	target_type VARCHAR(32) NOT NULL, 
	target_id INTEGER NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	applicant_id INTEGER NOT NULL, 
	approver_id INTEGER, 
	reason VARCHAR(255), 
	comment VARCHAR(255), 
	approved_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(applicant_id) REFERENCES users (id), 
	FOREIGN KEY(approver_id) REFERENCES users (id)
);

CREATE TABLE audit_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	target_type VARCHAR(32) NOT NULL, 
	target_id INTEGER NOT NULL, 
	detail TEXT NOT NULL, 
	ip VARCHAR(64) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE materials (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(128) NOT NULL, 
	material_type VARCHAR(32) NOT NULL, 
	storage_path VARCHAR(255) NOT NULL, 
	url VARCHAR(255) NOT NULL, 
	mime_type VARCHAR(128) NOT NULL, 
	file_size INTEGER NOT NULL, 
	file_hash VARCHAR(64) NOT NULL, 
	tags TEXT NOT NULL, 
	owner_id INTEGER, 
	enabled INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE TABLE templates (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(128) NOT NULL, 
	category VARCHAR(64) NOT NULL, 
	msg_type VARCHAR(32) NOT NULL, 
	content TEXT NOT NULL, 
	variable_schema TEXT NOT NULL, 
	default_variables TEXT NOT NULL, 
	is_system INTEGER NOT NULL, 
	owner_id INTEGER, 
	enabled INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE TABLE messages (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	source_type VARCHAR(32) NOT NULL, 
	source_id INTEGER, 
	group_id INTEGER NOT NULL, 
	template_id INTEGER, 
	msg_type VARCHAR(32) NOT NULL, 
	rendered_content TEXT NOT NULL, 
	request_payload TEXT NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	scheduled_at DATETIME, 
	sent_at DATETIME, 
	retry_count INTEGER NOT NULL, 
	created_by INTEGER, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES `groups` (id), 
	FOREIGN KEY(template_id) REFERENCES templates (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE schedules (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(128) NOT NULL, 
	group_id INTEGER NOT NULL, 
	template_id INTEGER, 
	msg_type VARCHAR(32) NOT NULL, 
	content_snapshot TEXT NOT NULL, 
	variables TEXT NOT NULL, 
	schedule_type VARCHAR(32) NOT NULL, 
	cron_expr VARCHAR(64), 
	run_at DATETIME, 
	timezone VARCHAR(64) NOT NULL, 
	skip_weekends INTEGER NOT NULL, 
	skip_dates TEXT NOT NULL, 
	require_approval INTEGER NOT NULL, 
	approval_status VARCHAR(32) NOT NULL, 
	enabled INTEGER NOT NULL, 
	next_run_at DATETIME, 
	owner_id INTEGER, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES `groups` (id), 
	FOREIGN KEY(template_id) REFERENCES templates (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE TABLE message_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	message_id INTEGER NOT NULL, 
	request_payload TEXT NOT NULL, 
	response_payload TEXT NOT NULL, 
	http_status INTEGER NOT NULL, 
	success INTEGER NOT NULL, 
	latency_ms INTEGER NOT NULL, 
	error_code VARCHAR(64), 
	error_message VARCHAR(255), 
	attempt_no INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(message_id) REFERENCES messages (id)
);

