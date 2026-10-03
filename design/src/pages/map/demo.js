// 所有楼层、教室、活动、树洞消息和距离均为设计演示，非实时信息。
export const demoLocation = [175, 135]; // 与地图蓝点、初始相机和定位按钮共用，单位米。
export const venues = [
  { id: '444991872', short: '理科教学楼', floors: 4, label: '理教', rooms: ['101', '208', '302', '401'] },
  { id: '188711087', short: '百周年纪念讲堂', floors: 3, label: '讲堂', rooms: ['大厅', '多功能厅', '排练厅'] },
  { id: '240825557', short: '第二教学楼', floors: 5, label: '二教', rooms: ['101', '203', '301', '402', '501'] },
  { id: '226702307', short: '第一教学楼', floors: 3, label: '一教', rooms: ['101', '201', '301'] },
];
export const activities = [
  { id: 'ai', building: '444991872', floor: 2, room: '208', title: 'AI 与我们的日常', type: 'lecture', category: '讲座', time: '14:00–15:30', source: '校园活动公告', distance: '120 m', interest: '科技 · 兴趣匹配', description: '从校园生活里的小问题出发，一起聊聊人工智能如何改变日常。欢迎带着问题来。' },
  { id: 'salon', building: '444991872', floor: 3, room: '302', title: '青年学术沙龙', type: 'lecture', category: '讲座', time: '16:00–17:30', source: '院系公告', distance: '120 m', interest: '学术探索', description: '跨学科的轻松交流，分享最近读到的一篇论文与一个新想法。' },
  { id: 'math', building: '444991872', floor: 1, room: '101', title: '数学分析 · 课程', type: 'course', category: '课程', time: '10:10–12:00', source: '课程安排示例', distance: '120 m', interest: '教室课程', description: '课程信息展示示例：教室、节次与授课安排。此处不接入真实课表。' },
  { id: 'film', building: '188711087', floor: 1, room: '大厅', title: '周末电影放映', type: 'culture', category: '文艺', time: '19:00–21:00', source: '讲堂公告', distance: '350 m', interest: '电影 · 兴趣匹配', description: '在校园里看一部电影，映后一起聊聊最喜欢的片段。' },
  { id: 'reading', building: '240825557', floor: 2, room: '203', title: '书页之间 · 读书会', type: 'culture', category: '文艺', time: '18:30–20:00', source: '社团公告', distance: '280 m', interest: '阅读 · 兴趣匹配', description: '带上一本喜欢的书，分享一个想推荐给大家的故事。' },
  { id: 'physics', building: '226702307', floor: 2, room: '201', title: '大学物理 · 课程', type: 'course', category: '课程', time: '13:00–14:50', source: '课程安排示例', distance: '200 m', interest: '教室课程', description: '课程与活动在同一楼层视图中呈现。这是一条固定课程样例。' },
];
export const filters = [{ id: 'all', label: '全部' }, { id: 'lecture', label: '讲座' }, { id: 'course', label: '课程' }, { id: 'culture', label: '文艺' }];
