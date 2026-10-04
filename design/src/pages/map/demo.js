// 所有楼层、教室、活动、树洞消息和距离均为设计演示，非实时信息。
export const demoLocation = [175, 135]; // 与地图蓝点、初始相机和定位按钮共用，单位米。
export const venues = [
  { id: '444991872', short: '理科教学楼', floors: 4, label: '理教', rooms: ['101', '208', '302', '401'] },
  { id: '188711087', short: '百周年纪念讲堂', floors: 3, label: '讲堂', rooms: ['大厅', '多功能厅', '排练厅'] },
  { id: '240825557', short: '第二教学楼', floors: 5, label: '二教', rooms: ['101', '203', '301', '402', '501'] },
  { id: '226702307', short: '第一教学楼', floors: 3, label: '一教', rooms: ['101', '201', '301'] },
];
export { activities, categories, mapFilters as filters } from '../../data/activities.js';
