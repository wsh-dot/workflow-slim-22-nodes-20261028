-- 内置 CBS 页面授权初始化脚本。
-- 依赖 001__init_schema.sql 和 002__initial_data.sql；本文件独立手动执行，不加入初始化顺序。
-- 页面地址：/system/cbsKnowledge；仅开放只读查询。
BEGIN;

INSERT INTO sys_resource_category (id, parent_id, name, module, sort, remark)
SELECT '93a00000-0000-4000-8000-000000000001', '8a81a31b5d30a444015d30db561a0020',
       'CBS知识库', 'cbs', 9, 'CBS知识库页面资源'
WHERE NOT EXISTS (
    SELECT 1 FROM sys_resource_category
    WHERE parent_id = '8a81a31b5d30a444015d30db561a0020' AND name = 'CBS知识库'
);

INSERT INTO sys_permission_category (id, parent_id, name, sort, remark)
SELECT '93a00000-0000-4000-8000-000000000002', '8a8196e85d4dd95d015d4ddf23a60002',
       'CBS知识库', 8, 'CBS知识库只读权限'
WHERE NOT EXISTS (
    SELECT 1 FROM sys_permission_category
    WHERE parent_id = '8a8196e85d4dd95d015d4ddf23a60002' AND name = 'CBS知识库'
);

INSERT INTO sys_menu (id, parent_id, code, title, name, url, view_, isleaf, level_, expanded, type)
SELECT '93a00000-0000-4000-8000-000000000003', '8a81a22b42ea70d30142ea8062390075',
       '300112', 'CBS知识库', 'cbsKnowledge', '/system/cbsKnowledge', 1, 1, 2, 1, 0
WHERE NOT EXISTS (
    SELECT 1 FROM sys_menu WHERE id = '93a00000-0000-4000-8000-000000000003'
       OR url = '/system/cbsKnowledge'
);

INSERT INTO sys_permission (id, name, module, permission, status, orderno, categoryid)
SELECT '93a00000-0000-4000-8000-000000000004', 'CBS知识库查看', 'cbs',
       'cbs_knowledge_view_permission', 1, 17, c.id
FROM sys_permission_category c
WHERE c.parent_id = '8a8196e85d4dd95d015d4ddf23a60002' AND c.name = 'CBS知识库'
  AND NOT EXISTS (SELECT 1 FROM sys_permission WHERE permission = 'cbs_knowledge_view_permission');

INSERT INTO sys_resource (id, menuid, name, module, resource_, type, categoryid, status)
SELECT '93a00000-0000-4000-8000-000000000005', m.id, 'CBS知识库查看', 'cbs',
       'cbs_knowledge_view_resource', 'TAG', c.id, 1
FROM sys_menu m
JOIN sys_resource_category c
  ON c.parent_id = '8a81a31b5d30a444015d30db561a0020' AND c.name = 'CBS知识库'
WHERE m.url = '/system/cbsKnowledge'
  AND NOT EXISTS (SELECT 1 FROM sys_resource WHERE resource_ = 'cbs_knowledge_view_resource');

INSERT INTO sys_permission_resource (id, permissionid, resourceid)
SELECT '93a00000-0000-4000-8000-000000000006', p.id, r.id
FROM sys_permission p
CROSS JOIN sys_resource r
WHERE p.permission = 'cbs_knowledge_view_permission'
  AND r.resource_ = 'cbs_knowledge_view_resource'
  AND NOT EXISTS (
      SELECT 1 FROM sys_permission_resource pr
      WHERE pr.permissionid = p.id AND pr.resourceid = r.id
  );

-- 默认系统管理员通过菜单权限查询页面路由，因此一并授予查看权限。
INSERT INTO sys_group_permission (id, groupid, permissionid, status)
SELECT '93a00000-0000-4000-8000-000000000007', g.id, p.id, 1
FROM sys_group g
CROSS JOIN sys_permission p
WHERE g.code = 'SYSTEM_ADMIN'
  AND p.permission = 'cbs_knowledge_view_permission'
  AND NOT EXISTS (
      SELECT 1 FROM sys_group_permission gp
      WHERE gp.groupid = g.id AND gp.permissionid = p.id
  );

COMMIT;
