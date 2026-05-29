import request from './request'

// 获取项目成员列表
export function getProjectMembers(projectId) {
  return request({
    url: `/project-members/${projectId}`,
    method: 'get'
  })
}

// 添加项目成员
export function addProjectMember(data) {
  return request({
    url: '/project-members',
    method: 'post',
    data
  })
}

// 更新成员角色
export function updateMemberRole(memberId, data) {
  return request({
    url: `/project-members/detail/${memberId}`,
    method: 'put',
    data
  })
}

// 移除项目成员
export function removeMember(memberId) {
  return request({
    url: `/project-members/detail/${memberId}`,
    method: 'delete'
  })
}
