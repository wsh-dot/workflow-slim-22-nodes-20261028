-- 系统管理、默认管理员、数字字典和分类初始化数据。
-- 依赖 001__init_schema.sql；执行时会清空本脚本负责初始化的数据表并重新写入初始数据。
-- 注意：执行后这些表中的原有数据不可恢复；请仅用于初始化数据库。
BEGIN;

DELETE FROM sys_group_permission;
DELETE FROM sys_user_permission;
DELETE FROM sys_permission_resource;
DELETE FROM sys_user_group;
DELETE FROM sys_user_uid;
DELETE FROM sys_group;
DELETE FROM sys_user;
DELETE FROM sys_menu;
DELETE FROM sys_resource;
DELETE FROM sys_permission;
DELETE FROM sys_permission_category;
DELETE FROM sys_resource_category;
DELETE FROM sys_user_category;
DELETE FROM sys_group_category;
DELETE FROM pb_base_option;

-- 菜单、资源、权限及管理员角色关系

-- 初始化系统管理菜单、资源、权限及默认管理员关联数据。
-- 需先执行 001__init_schema.sql；按项目 SQL 发布流程由人工审核并执行。
INSERT INTO sys_group_category (id, name, level_, sort, parent_id, isleaf)
VALUES
('8a81a36042bc4f860142bc4f952a0000', '角色类型', 0, 0, NULL, 0),
('8a81a89f46b6b0c90146f5cf8d364a87', '基础角色', 0, 9, '8a81a36042bc4f860142bc4f952a0000', 1);
INSERT INTO sys_user_category (id, parent_id, name, longname, sort, delete_status)
VALUES ('6ce3b2dc-79a9-4a4d-a512-3c0b2077d001', NULL,
        '长庆工程设计有限公司', '长庆工程设计有限公司', 0, 0);
INSERT INTO sys_group (id, categoryid, code, name, status, createtime)
VALUES ('8a8196ec5aa2bdda015aa2efd1600025', '8a81a89f46b6b0c90146f5cf8d364a87',
        'SYSTEM_ADMIN', '系统管理员', 1, to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'));
INSERT INTO sys_resource_category (id, parent_id, name, module, sort, remark)
VALUES
('8a81a3165be99958015be5ee01110110',NULL,'资源管理',NULL,0),
('8a81a31b5d30a444015d30db561a0020','8a81a3165be99958015be5ee01110110','系统管理','system',30),
('8a81a82c5d40086c015d400f3c84000e','8a81a31b5d30a444015d30db561a0020','用户机构管理','system',1),
('8a81a82c5d40086c015d400f5f650010','8a81a31b5d30a444015d30db561a0020','资源管理','system',2),
('8a81a82c5d40086c015d400f86fd0012','8a81a31b5d30a444015d30db561a0020','权限管理','system',3),
('8a81a82c5d40086c015d400fac330014','8a81a31b5d30a444015d30db561a0020','角色管理','system',4),
('8a81a82c5d40086c015d400fce160016','8a81a31b5d30a444015d30db561a0020','菜单管理','system',5),
('8a81a82c5d40086c015d400ff9f40018','8a81a31b5d30a444015d30db561a0020','数据字典','system',7),
('8a81a3e85dc06330015dc06884910003','8a81a31b5d30a444015d30db561a0020','日志管理','system',6);
-- 可路由叶子菜单使用当前前端白名单中的 code/url；组织机构功能并入用户机构页，不单独注册路由。
-- 导出菜单树中的外部应用父节点不属于本项目，故以菜单管理作为树根，系统管理保留为其子级。
INSERT INTO sys_menu (id, code, title, name, url, view_, isleaf, level_, expanded, type)
VALUES ('8a81a2e345459a96014545b9410f00da', '30', '菜单管理', 'system', '/', 0, 0, 0, 0, 0);
INSERT INTO sys_menu (id, parent_id, code, title, name, url, view_, isleaf, level_, expanded, type)
VALUES ('8a81a22b42ea70d30142ea8062390075','8a81a2e345459a96014545b9410f00da','3001','系统管理','systemManager','/system/systemManager',1,0,1,0,0);
INSERT INTO sys_menu (id, parent_id, code, title, name, url, view_, isleaf, level_, expanded, type)
VALUES
('8a8196f4598667be015986dc17210007','8a81a22b42ea70d30142ea8062390075','300101','用户机构管理','account','/system/users',1,1,2,1,0),
('8a81a89f436fc50401437019b1b50652','8a81a22b42ea70d30142ea8062390075','300105','角色管理','group','/system/roles',1,1,2,1,0),
('8a81a89f436fc5040143701a0df10ac2','8a81a22b42ea70d30142ea8062390075','300104','权限管理','permission','/system/permissions',1,1,2,1,0),
('8a81a89f436fc50401437019e0dd0892','8a81a22b42ea70d30142ea8062390075','300103','资源管理','resource','/system/resources',1,1,2,1,0),
('8a81a89f436fc504014370197c5603b5','8a81a22b42ea70d30142ea8062390075','300106','菜单管理','menu','/system/menus',1,1,2,1,0),
('8a81a3e85dc06330015dc0681ccd0001','8a81a22b42ea70d30142ea8062390075','300107','日志管理','operationLog','/system/logs',1,1,2,1,0),
('8a81a8e442e61d020142f9575d155d80','8a81a22b42ea70d30142ea8062390075','300110','数据字典','option','/system/options',1,1,2,1,0);
-- 初始化权限标识；组织机构操作复用用户机构管理权限。
-- 先建立权限分类，权限插入时直接写入最终分类。
INSERT INTO sys_permission_category (id, parent_id, name, sort, remark)
VALUES
    ('8a81a36042bc4f860142bc4f952a0000', NULL, '权限管理', 0, NULL),
    ('8a8196e85d4dd95d015d4ddf23a60002', '8a81a36042bc4f860142bc4f952a0000', '系统管理', 30, NULL),
    ('8a8196e85d4dd95d015d4de02dbc000b', '8a8196e85d4dd95d015d4ddf23a60002', '用户机构管理', 0, NULL),
    ('8a8196e85d4dd95d015d4de052fc000d', '8a8196e85d4dd95d015d4ddf23a60002', '资源管理', 1, NULL),
    ('8a8196e85d4dd95d015d4de071f0000f', '8a8196e85d4dd95d015d4ddf23a60002', '权限管理', 2, NULL),
    ('8a8196e85d4dd95d015d4ddf85470007', '8a8196e85d4dd95d015d4ddf23a60002', '角色管理', 3, NULL),
    ('8a8196e85d4dd95d015d4ddffdb80009', '8a8196e85d4dd95d015d4ddf23a60002', '菜单管理', 4, NULL),
    ('8a81a3e85dc06330015dc06c092a0012', '8a8196e85d4dd95d015d4ddf23a60002', '日志管理', 5, NULL),
    ('8a8196e85d4dd95d015d4de09c430011', '8a8196e85d4dd95d015d4ddf23a60002', '数据字典', 6, NULL);
INSERT INTO sys_permission (id, name, module, permission, status, orderno, categoryid)
VALUES
('8a8196e95a6f0113015a6f1b5f440088','用户机构管理查看','system','system_userOrg_view_permission',1,1,'8a8196e85d4dd95d015d4de02dbc000b'),
('8a8196e95a6f0113015a6f1b1a150086','用户机构管理维护','system','system_userOrg_edit_permission',1,2,'8a8196e85d4dd95d015d4de02dbc000b'),
('8a8196e95a6f0113015a6f19c40d0080','角色管理查看','system','system_role_view_permission',1,5,'8a8196e85d4dd95d015d4ddf85470007'),
('8a81a82c5dc4d51a015e7a304a0d03c8','角色管理维护','system','system_role_edit_permission',1,6,'8a8196e85d4dd95d015d4ddf85470007'),
('8a8196e95a6f0113015a6f1ca15e0090','权限管理查看','system','system_permission_view_permission',1,7,'8a8196e85d4dd95d015d4de071f0000f'),
('8a8196e95a6f0113015a6f1c5c8c008e','权限管理维护','system','system_permission_edit_permission',1,8,'8a8196e85d4dd95d015d4de071f0000f'),
('8a8196e95a6f0113015a6f1c0e47008c','资源管理查看','system','system_resource_view_permission',1,9,'8a8196e85d4dd95d015d4de052fc000d'),
('8a8196e95a6f0113015a6f1bc960008a','资源管理维护','system','system_resource_edit_permission',1,10,'8a8196e85d4dd95d015d4de052fc000d'),
('8a8196e95a6f0113015a6f1a4a990082','菜单管理查看','system','system_menu_view_permission',1,11,'8a8196e85d4dd95d015d4ddffdb80009'),
('8a8196e95a6f0113015a6f1ac2570084','菜单管理维护','system','system_menu_edit_permisson',1,12,'8a8196e85d4dd95d015d4ddffdb80009'),
('8a8196e95a7e26ae015a7e468dfd0023','数据字典查看','system','system_sjzd_menu_permission',1,13,'8a8196e85d4dd95d015d4de09c430011'),
('8a81a3b85e7520cd015e752813420018','数据字典维护','system','system_sjrd_edit_permission',1,14,'8a8196e85d4dd95d015d4de09c430011'),
('8a81a3e85dc06330015dc06ce8860014','日志管理查看','system','system_operationLog_menu_permission',1,15,'8a81a3e85dc06330015dc06c092a0012');
INSERT INTO sys_resource (id, menuid, name, module, resource_, type, categoryid, status)
SELECT v.id, v.menuid, v.name, 'system', v.resource_, v.type, v.categoryid, 1 FROM (VALUES
('8a8196e95a6f0113015a6f11a4f80070','8a8196f4598667be015986dc17210007','用户机构管理查看','system_userOrg_view_resource','TAG','8a81a82c5d40086c015d400f3c84000e'),
('8a8196e95a6f0113015a6f112d79006e','8a8196f4598667be015986dc17210007','用户机构管理维护','system_userOrg_edit_resource','TAG','8a81a82c5d40086c015d400f3c84000e'),
('8a8196e95a6f0113015a6f0e1ede0066','8a81a89f436fc50401437019b1b50652','角色管理查看','system_role_view_resource','TAG','8a81a82c5d40086c015d400fac330014'),
('8a8196e95a6f0113015a6f09dcb80064','8a81a89f436fc50401437019b1b50652','角色管理维护','system_role_edit_resource','TAG','8a81a82c5d40086c015d400fac330014'),
('8a8196e95a6f0113015a6f0f991f006a','8a81a89f436fc504014370197c5603b5','菜单管理查看','system_menu_view_resource','TAG','8a81a82c5d40086c015d400fce160016'),
('8a8196e95a6f0113015a6f10379f006c','8a81a89f436fc504014370197c5603b5','菜单管理维护','system_menu_edit_resource','TAG','8a81a82c5d40086c015d400fce160016'),
('8a8196e95a6f0113015a6f128fa40074','8a81a89f436fc50401437019e0dd0892','资源管理查看','system_resource_view_resource','TAG','8a81a82c5d40086c015d400f5f650010'),
('8a8196e95a6f0113015a6f1222230072','8a81a89f436fc50401437019e0dd0892','资源管理维护','system_resource_edit_resource','TAG','8a81a82c5d40086c015d400f5f650010'),
('8a8196e95a6f0113015a6f14acf9007a','8a81a89f436fc5040143701a0df10ac2','权限管理查看','system_permission_view_resource','TAG','8a81a82c5d40086c015d400f86fd0012'),
('8a8196e95a6f0113015a6f1343160076','8a81a89f436fc5040143701a0df10ac2','权限管理维护','system_permission_edit_resource','TAG','8a81a82c5d40086c015d400f86fd0012'),
('dd000000000000000000000000000001','8a81a8e442e61d020142f9575d155d80','数据字典查看','system_sjrd_view_resource','TAG','8a81a82c5d40086c015d400ff9f40018'),
('dd000000000000000000000000000002','8a81a8e442e61d020142f9575d155d80','数据字典维护','system_sjrd_edit_resource','TAG','8a81a82c5d40086c015d400ff9f40018'),
('8a8196e95a7e26ae015a7e44c7e60021','8a81a8e442e61d020142f9575d155d80','数据字典菜单','system_sjrd_menu_resource','MENU','8a81a82c5d40086c015d400ff9f40018'),
('8a81a3e85dc06330015dc06937790005','8a81a3e85dc06330015dc0681ccd0001','日志管理查看','system_operationLog_view_resource','TAG','8a81a3e85dc06330015dc06884910003'),
('8a81a3e85dc06330015dc069d9590008','8a81a3e85dc06330015dc0681ccd0001','日志管理维护','system_operationLog_edit_resource','TAG','8a81a3e85dc06330015dc06884910003'),
('8a81a3e85dc06330015dc06a56c2000a','8a81a3e85dc06330015dc0681ccd0001','日志管理菜单','system_operationLog_menu_resource','MENU','8a81a3e85dc06330015dc06884910003')
) AS v(id, menuid, name, resource_, type, categoryid);
INSERT INTO sys_permission_resource (id, permissionid, resourceid)
SELECT v.id, p.id, r.id FROM (VALUES
('b1e81430a1d2433596b0000000000001','system_userOrg_edit_permission','system_userOrg_edit_resource'),
('b1e81430a1d2433596b0000000000003','system_role_edit_permission','system_role_edit_resource'),
('b1e81430a1d2433596b0000000000004','system_menu_edit_permisson','system_menu_edit_resource'),
('b1e81430a1d2433596b0000000000005','system_resource_edit_permission','system_resource_edit_resource'),
('b1e81430a1d2433596b0000000000006','system_permission_edit_permission','system_permission_edit_resource'),
('8a8196e95a6f22c1015a6f244c1a0008','system_role_view_permission','system_role_view_resource'),
('8a8196e95a6f22c1015a6f24a77c000d','system_menu_view_permission','system_menu_view_resource'),
('8a8196e95a6f22c1015a6f25519a0017','system_userOrg_view_permission','system_userOrg_view_resource'),
('8a8196e95a6f22c1015a6f25d052001d','system_resource_view_permission','system_resource_view_resource'),
('8a8196e95a6f22c1015a6f2650dc0023','system_permission_view_permission','system_permission_view_resource'),
('dd000000000000000000000000000011','system_sjzd_menu_permission','system_sjrd_view_resource'),
('dd000000000000000000000000000012','system_sjrd_edit_permission','system_sjrd_edit_resource'),
('8a81a3e85dc06330015dc06eacba00d0','system_operationLog_menu_permission','system_operationLog_menu_resource'),
('8a81a3e85dc06330015dc06eacba00d1','system_operationLog_menu_permission','system_operationLog_view_resource'),
('8a81a3e85dc06330015dc06eacba00d2','system_operationLog_menu_permission','system_operationLog_edit_resource'),
('8a81a3e85dc06330015dc06eacba00d3','system_sjzd_menu_permission','system_sjrd_menu_resource')
) AS v(id, permission, resource_)
JOIN sys_permission p ON p.permission = v.permission
JOIN sys_resource r ON r.resource_ = v.resource_;

-- 默认管理员账号及角色授权

-- 初始化默认管理员账号及角色授权；账号凭据由本项目单独生成。
-- 此账号初始化依赖本脚本前面已建立菜单权限、角色及组织数据。
-- 请在首次登录后立即重置密码；重新执行本脚本会重建该初始化账号。
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM sys_group WHERE code = 'SYSTEM_ADMIN' AND status = 1) THEN
        RAISE EXCEPTION '初始化数据中未找到启用的系统管理员角色';
    END IF;
    IF (SELECT COUNT(*) FROM sys_permission WHERE module = 'system' AND status = 1
        AND permission IN (
            'system_userOrg_view_permission', 'system_userOrg_edit_permission',
            'system_role_view_permission', 'system_role_edit_permission',
            'system_permission_view_permission', 'system_permission_edit_permission',
            'system_resource_view_permission', 'system_resource_edit_permission',
            'system_menu_view_permission', 'system_menu_edit_permisson',
            'system_sjzd_menu_permission', 'system_sjrd_edit_permission', 'system_operationLog_menu_permission'
        )) <> 13 THEN
        RAISE EXCEPTION '默认权限未完整初始化，请检查本脚本前序权限初始化数据';
    END IF;
END $$;

INSERT INTO sys_user (id, category_id, account, pwd, name, regtime, logintimes, status,
                      orgadmin, delete_status, loginfailtimes)
VALUES ('efc05a6b-6afc-4ff5-a2ce-6621bdf3f854', '6ce3b2dc-79a9-4a4d-a512-3c0b2077d001', 'admin',
       '$2a$12$rDB01QhpEozBKpRnRJih3uBMCWsuWtaM/r4tftixQi4oxULopm1iy',
        '系统管理员', to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'), 0, 1, 1, 0, 0);

INSERT INTO sys_user_uid (id, user_id, type_, uid_, enable)
SELECT '0b0cbba7-fe6d-465b-a4bf-2e85c1a06a8b', u.id, 'account', 'admin', 1
FROM sys_user u
WHERE u.account = 'admin';

INSERT INTO sys_user_group (id, userid, groupid, status, orgid)
SELECT 'a965adee-0c32-4a3a-b506-2494a42b4d9a', u.id, g.id, 1, u.category_id
FROM sys_user u, sys_group g
WHERE u.account = 'admin' AND g.code = 'SYSTEM_ADMIN';

-- 将管理员角色关联到本项目完整系统管理权限集，便于后台查看和后续管理。
INSERT INTO sys_group_permission (id, groupid, permissionid, status)
SELECT defaults.id, g.id, p.id, 1
FROM (VALUES
    ('537506e6db12edcd31c3867ca1ae3349', 'system_userOrg_view_permission'),
    ('7dcfd283-cbe0-434e-82b8-335622a1e1dd', 'system_userOrg_edit_permission'),
    ('c0f106217dae1de6d0c4aa55384a3edc', 'system_role_view_permission'),
    ('3a976b1c27fcf51b6d4c1f5fb885518a', 'system_role_edit_permission'),
    ('c7084a972d5361eda84ec3eeb954764a', 'system_permission_view_permission'),
    ('3c5d9922-94d9-4693-84ca-dc7f3a069af1', 'system_permission_edit_permission'),
    ('d07a3f2569bb2f161de15181d35c0829', 'system_resource_view_permission'),
    ('a9f9108d-8f66-4ec3-becf-43f0282db4e5', 'system_resource_edit_permission'),
    ('c16bf71849a2dc19743b177091e3a117', 'system_menu_view_permission'),
    ('bb40a052c78b555de09b04fd90d2a2cb', 'system_menu_edit_permisson'),
    ('75738b08a45afb2fe705a1e02dc4bd34', 'system_sjzd_menu_permission'),
    ('b41a7441a8d82a3387eb71e96cbeae30', 'system_sjrd_edit_permission'),
    ('7a06a232d79cc141caeddd15b8bf0a30', 'system_operationLog_menu_permission')
) AS defaults(id, permission)
JOIN sys_permission p ON p.permission = defaults.permission AND p.status = 1
CROSS JOIN sys_group g
WHERE g.code = 'SYSTEM_ADMIN';

-- 基础数字字典

-- 初始化资源类型、权限类型、机构类型和菜单类型字典；机构类型仅保留“设计单位”。
-- 子项 okey 使用对应分类编码及两位子项序号。
INSERT INTO pb_base_option (id, parent_id, name, okey, lable, ovalue, sort, status, remark, item)
VALUES
('dd000000000000000000000000000020', NULL, '数字字典', '00', NULL, '00', 0, 1, '数字字典分类根节点', NULL),
('8a81965e5a3a1106015a3a5cb69a0012', 'dd000000000000000000000000000020', '资源类型', '02', NULL, '02', 2, 1, '资源类型', NULL),
('8a81965e5a3a1106015a3a5cf2e20013', '8a81965e5a3a1106015a3a5cb69a0012', 'TAG', '0201', NULL, 'TAG', 1, 1, NULL, NULL),
('8a81965e5a3a1106015a3a5d14bd0014', '8a81965e5a3a1106015a3a5cb69a0012', 'URL', '0202', NULL, 'URL', 2, 1, NULL, NULL),
('8a81965e5a3b3b32015a3b69195e0005', 'dd000000000000000000000000000020', '权限类型', '03', NULL, '03', 3, 1, '权限类型', NULL),
('8a81965e5a3b3b32015a3b69aee20006', '8a81965e5a3b3b32015a3b69195e0005', 'Anonymous', '0301', NULL, 'Anonymous', 1, 1, 'Anonymous', NULL),
('8a81965e5a3b3b32015a3b69d44a0007', '8a81965e5a3b3b32015a3b69195e0005', 'Member', '0302', NULL, 'Member', 2, 1, 'Member', NULL),
('8a81965e5a3b3b32015a3b6a17bb0008', '8a81965e5a3b3b32015a3b69195e0005', 'Manager', '0303', NULL, 'Manager', 3, 1, 'Manager', NULL),
('8a81965e5a44cf93015a44da36040000', 'dd000000000000000000000000000020', '机构类型', '04', NULL, '04', 4, 1, '机构类型，用于业务系统机构选择上。', NULL),
('8a819ee7828043e101828ca6634a0814', '8a81965e5a44cf93015a44da36040000', '设计单位', '0405', NULL, '0405', 5, 1, NULL, NULL),
('8a81963a5a8df683015a8dfadb460000', 'dd000000000000000000000000000020', '菜单类型', '06', NULL, '06', 6, 1, NULL, NULL),
('8a81963a5a8df683015a8dfc2f770001', '8a81963a5a8df683015a8dfadb460000', '普通菜单', '0601', NULL, '0', 1, 1, NULL, NULL),
('8a81963a5a8df683015a8dfc96350002', '8a81963a5a8df683015a8dfadb460000', '桌面', '0602', NULL, '1', 2, 1, NULL, NULL),
('8a81963a5a8df683015a8dfcdcf60003', '8a81963a5a8df683015a8dfadb460000', '新页面', '0603', NULL, '2', 3, 1, NULL, NULL);
COMMIT;

-- 智能组价部分权限
-- 初始化智能组价模块（项目管理、历史数据、知识库维护）的分类、权限、资源及权限资源关联。
-- 先插入分类，再插入引用分类的权限和资源，最后建立权限资源映射。

BEGIN;

-- 初始化智能组价相关权限分类和资源分类。
INSERT INTO sys_permission_category (id, parent_id, name, sort, remark)
VALUES
('256a38ba-b897-4567-aefb-59a95257bdd3', '8a81a36042bc4f860142bc4f952a0000', '智能组价', 2, NULL),
('8d561156-ef8f-408a-a48d-44cf55cfc2ee', '256a38ba-b897-4567-aefb-59a95257bdd3', '项目管理', 1, NULL),
('bb8b01c5-aadd-4947-b3ee-71017f801eb3', '256a38ba-b897-4567-aefb-59a95257bdd3', '历史数据', 2, NULL),
('ec5719bb-c234-47bf-b191-5173ca805029', '256a38ba-b897-4567-aefb-59a95257bdd3', '知识库维护', 3, NULL);

INSERT INTO sys_resource_category (id, parent_id, name, module, sort, remark)
VALUES
('b5bd62ba-33a2-4036-a32f-6d4580f46125', '8a81a3165be99958015be5ee01110110', '智能组价', 'smartCost', 1, NULL),
('b5ff4455-88a0-40d2-bcd4-6b43105329ef', 'b5bd62ba-33a2-4036-a32f-6d4580f46125', '项目管理', 'smartCost', 1, NULL),
('f9913b85-5c6c-44b2-98d9-efcbede1a465', 'b5bd62ba-33a2-4036-a32f-6d4580f46125', '历史数据', 'smartCost', 2, NULL),
('790f06c0-6b89-4a1a-89c7-97bcd4e00a1e', 'b5bd62ba-33a2-4036-a32f-6d4580f46125', '知识库维护', 'knowledge', 3, NULL);

-- 初始化智能组价相关权限标识和资源，权限插入时直接写入最终分类。
INSERT INTO sys_permission (id, name, module, permission, type_, description, status, categoryid, orderno)
VALUES
('7d062c69-9944-435b-90c4-873c68b0d990', '历史数据-查看', 'smartCost', 'smart_cost_lssj_permission', NULL, NULL, 1, 'bb8b01c5-aadd-4947-b3ee-71017f801eb3', 1),
('b5916788-9dc0-46ef-b1e2-62661a1b2511', '项目管理-查看', 'smartCost', 'smart_cost_xmgl_permission', NULL, NULL, 1, '8d561156-ef8f-408a-a48d-44cf55cfc2ee', 1),
('f2617ddf-16ab-4920-8681-cd86eaf5fe9a', '知识库维护-查看', 'smartCost', 'smart_cost_zskwh_permission', NULL, NULL, 1, 'ec5719bb-c234-47bf-b191-5173ca805029', 1);

-- 资源插入时写入菜单挂载和最终分类。
INSERT INTO sys_resource (id, menuid, name, module, resource_, type, description, categoryid, status)
VALUES
('76e9a77d-b694-4607-8ac9-9b9f568c8831', '7163a9de-4ce7-4165-ad17-0be020c6fde0', '项目管理-查看', 'smartCost', 'smart_cost_xmgl_resource', NULL, NULL, 'b5ff4455-88a0-40d2-bcd4-6b43105329ef', 1),
('1fb653cb-ee34-4e10-94c4-e190fe5eff78', '5746a2d8-bd64-421c-a6c5-72dd69e0253b', '历史数据-查看', 'smartCost', 'smart_cost_lssj_resource', NULL, NULL, 'f9913b85-5c6c-44b2-98d9-efcbede1a465', 1),
('5a5ddfa2-305a-47c4-985d-d393aba3ecad', '125d51a0-ac3b-430e-993c-6bc44dd2fc72', '知识库维护-查看', 'smartCost', 'smart_cost_zskwh_resource', NULL, NULL, '790f06c0-6b89-4a1a-89c7-97bcd4e00a1e', 1);

-- 建立权限与资源的映射关系。
INSERT INTO sys_permission_resource (id, permissionid, resourceid)
VALUES
('c52661e2-2194-4ddc-9db0-b83f4f5d1f50', 'b5916788-9dc0-46ef-b1e2-62661a1b2511', '76e9a77d-b694-4607-8ac9-9b9f568c8831'),
('722d2dbd-1364-4d4d-9779-ba6899633f0b', 'f2617ddf-16ab-4920-8681-cd86eaf5fe9a', '5a5ddfa2-305a-47c4-985d-d393aba3ecad'),
('5f6f36fd-3592-4490-9aa7-2702608b4fc9', '7d062c69-9944-435b-90c4-873c68b0d990', '1fb653cb-ee34-4e10-94c4-e190fe5eff78');

-- AI 文件处理状态字典：三个处理节点（工程量编制、定额匹配、价格匹配），各有待处理、已处理两种状态。
INSERT INTO pb_base_option (id, parent_id, name, okey, lable, ovalue, sort, status, remark, item)
VALUES
    ('b6000000-0000-4000-8000-000000000060', 'dd000000000000000000000000000020', 'AI文件处理状态', '21', NULL, '21', 15, 1, 'AI文件处理状态，用于 sc_file.status', NULL),
    ('b6000000-0000-4000-8000-000000000061', 'b6000000-0000-4000-8000-000000000060', '工程量编制-待处理', '2101', NULL, '2101', 1, 1, NULL, NULL),
    ('b6000000-0000-4000-8000-000000000062', 'b6000000-0000-4000-8000-000000000060', '工程量编制-已处理', '2102', NULL, '2102', 2, 1, NULL, NULL),
    ('b6000000-0000-4000-8000-000000000063', 'b6000000-0000-4000-8000-000000000060', '定额匹配-待处理', '2103', NULL, '2103', 3, 1, NULL, NULL),
    ('b6000000-0000-4000-8000-000000000064', 'b6000000-0000-4000-8000-000000000060', '定额匹配-已处理', '2104', NULL, '2104', 4, 1, NULL, NULL),
    ('b6000000-0000-4000-8000-000000000065', 'b6000000-0000-4000-8000-000000000060', '价格匹配-待处理', '2105', NULL, '2105', 5, 1, NULL, NULL),
    ('b6000000-0000-4000-8000-000000000066', 'b6000000-0000-4000-8000-000000000060', '价格匹配-已处理', '2106', NULL, '2106', 6, 1, NULL, NULL);
COMMIT;
