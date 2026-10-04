// 地图和日历共用同一份活动。课程只在地图分类里单独出现，日历不提供这一筛选项。
export const categories = {
  lecture: { id: 'lecture', label: '讲座', pencil: 'pink', icon: 'spark', floorIcon: 'megaphone', calendarIcon: 'speaker', mark: '#e88880' },
  activity: { id: 'activity', label: '活动', pencil: 'lavender', icon: 'star', floorIcon: 'flag', calendarIcon: 'people', mark: '#ab94de' },
  course: { id: 'course', label: '课程', pencil: 'blue', icon: 'grid', floorIcon: 'people', calendarIcon: 'book', mark: '#6aaee8' },
  show: { id: 'show', label: '演出', pencil: 'mint', icon: 'flag', floorIcon: 'megaphone', calendarIcon: 'music', mark: '#3eae86' },
};

const order = ['lecture', 'activity', 'course', 'show'];
export const mapFilters = [
  { id: 'all', label: '全部', pencil: 'yellow' },
  ...order.map(id => ({ id, label: categories[id].label, pencil: categories[id].pencil })),
];
export const calendarFilters = mapFilters.filter(item => item.id !== 'course');

const halls = {
  li: '444991872',
  hall: '188711087',
  two: '240825557',
  one: '226702307',
};
const distanceOf = {
  [halls.li]: '120 m',
  [halls.hall]: '350 m',
  [halls.two]: '280 m',
  [halls.one]: '200 m',
};

const records = [
  { id: 'ai', title: 'AI 与我们的日常', chip: 'AI讲座', category: 'lecture', date: '2026-10-03', start: '14:00', end: '15:30', place: '理科教学楼208', building: halls.li, floor: 2, room: '208', source: '校园活动公告', description: '从校园生活里的小问题出发，一起聊聊人工智能如何改变日常。欢迎带着问题来。', detail: '这场讲座从选课、找资料、写笔记这些日常小事讲起，看看人工智能已经怎样嵌进校园生活。主讲人会用几个可以当场试的例子，说明模型能帮上忙的地方，也会谈它容易出错的时候。后半段留出提问，欢迎带着自己的使用习惯或顾虑来。不需要提前报名，按现场座位入座即可。' },
  { id: 'salon', title: '青年学术沙龙', chip: '沙龙', category: 'lecture', date: '2026-10-03', start: '16:00', end: '17:30', place: '理科教学楼302', building: halls.li, floor: 3, room: '302', source: '院系公告', description: '跨学科的轻松交流，分享最近读到的一篇论文与一个新想法。', detail: '沙龙不设长篇报告。每位参与者用几分钟讲最近读到的一篇论文，或一个还没想完的新想法。不同专业的同学可以追问、补充例子，也可以只是来听。现场会简单计时，保证每个人都有开口的机会。适合想认识跨学科同伴、又不想听完一整场正式讲座的时候来。' },
  { id: 'math', title: '数学分析 · 课程', chip: '数学', category: 'course', date: '2026-10-03', start: '10:10', end: '12:00', place: '理科教学楼101', building: halls.li, floor: 1, room: '101', source: '课程安排示例', description: '课程信息展示示例：教室、节次与授课安排。此处不接入真实课表。', detail: '这是一门课程在详情页里的展示示例，用来把教室、节次和授课安排写在同一处。页面上的时间与地点对应示例课表，并不接入真实选课系统。课堂上按例题推进，课前可以先看本周习题，下课后也能回到这里核对教室和节次。' },
  { id: 'film', title: '周末电影放映', chip: '电影', category: 'show', date: '2026-10-03', start: '19:00', end: '21:00', place: '百周年纪念讲堂', building: halls.hall, floor: 1, room: '大厅', source: '讲堂公告', description: '在校园里看一部电影，映后一起聊聊最喜欢的片段。', detail: '周末在百周年纪念讲堂放映一部电影。开场前会用几分钟介绍片长，以及看片时可以留意的地方；正片结束后留一段不正式的交流，大家说说自己最喜欢的片段。座位先到先坐，无需报名。如果只想安静看完再离开，也可以在交流开始时离场。' },
  { id: 'reading', title: '书页之间 · 读书会', chip: '读书', category: 'activity', date: '2026-10-03', start: '18:30', end: '20:00', place: '第二教学楼203', building: halls.two, floor: 2, room: '203', source: '社团公告', description: '带上一本喜欢的书，分享一个想推荐给大家的故事。', detail: '读书会每次围绕你带来的那本书，用自己的话讲一个想推荐的故事，或一段印象深的话。不要求大家读完同一本，也不用准备讲稿。分享之后可以互相提问，或只是记下下次想借的书名。适合晚饭后来坐一会儿，认识同样爱看书的同学。' },
  { id: 'physics', title: '大学物理 · 课程', chip: '物理', category: 'course', date: '2026-10-03', start: '13:00', end: '14:50', place: '第一教学楼201', building: halls.one, floor: 2, room: '201', source: '课程安排示例', description: '课程与活动在同一楼层视图中呈现。这是一条固定课程样例。', detail: '这是大学物理的课程样例，用来演示课程和活动可以出现在同一栋楼的详情页里。这里列出本节的时间和教室，方便从地图或日历点进来后核对。内容为固定演示，不代表真实排课；到教室后仍以当周板书和老师通知为准。' },
  { id: 'oct02-seminar', title: '数据结构答疑课', chip: '答疑', category: 'activity', date: '2026-10-02', start: '16:00', end: '17:30', place: '理科教学楼103', building: halls.li, floor: 1, room: '103' },
  { id: 'oct03-ai', title: '大模型与智能体讲座', chip: 'AI讲座', category: 'lecture', date: '2026-10-03', start: '14:00', end: '15:30', place: '理科教学楼208', building: halls.li, floor: 2, room: '208' },
  { id: 'oct03-photo', title: '校园摄影工作坊', chip: '摄影', category: 'activity', date: '2026-10-03', start: '16:00', end: '17:30', place: '新太阳活动中心' },
  { id: 'oct03-film', title: '悬疑电影放映', chip: '电影', category: 'show', date: '2026-10-03', start: '19:00', end: '21:30', place: '百周年纪念讲堂', building: halls.hall, floor: 1, room: '大厅' },
  { id: 'oct04-club', title: '学生会例会', chip: '社团', category: 'activity', date: '2026-10-04', start: '10:00', end: '11:30', place: '新太阳活动中心' },
  { id: 'oct04-volunteer', title: '志愿讲解培训', chip: '志愿', category: 'activity', date: '2026-10-04', start: '14:00', end: '15:30', place: '校史馆' },
  { id: 'oct04-dance', title: '舞蹈社排练', chip: '社团', category: 'activity', date: '2026-10-04', start: '16:00', end: '18:00', place: '五四体育馆' },
  { id: 'oct05-innovate', title: '创新创业讲座', chip: '创新讲座', category: 'lecture', date: '2026-10-05', start: '10:00', end: '11:30', place: '理科教学楼207', building: halls.li, floor: 2, room: '207' },
  { id: 'oct06-photo', title: '夜拍校园活动', chip: '摄影', category: 'activity', date: '2026-10-06', start: '10:00', end: '12:00', place: '未名湖' },
  { id: 'oct06-volunteer', title: '图书馆志愿整理', chip: '志愿', category: 'activity', date: '2026-10-06', start: '14:00', end: '16:00', place: '图书馆' },
  { id: 'oct06-film', title: '经典电影放映', chip: '电影', category: 'show', date: '2026-10-06', start: '18:00', end: '20:30', place: '百周年纪念讲堂', building: halls.hall, floor: 1, room: '大厅' },
  { id: 'oct07-film', title: '纪录片放映', chip: '电影', category: 'show', date: '2026-10-07', start: '10:00', end: '12:00', place: '二教107', building: halls.two, floor: 1, room: '107' },
  { id: 'oct07-drama', title: '话剧社排练', chip: '社团', category: 'activity', date: '2026-10-07', start: '16:00', end: '18:00', place: '百年讲堂排练厅', building: halls.hall, floor: 3, room: '排练厅' },
  { id: 'oct08-humanities', title: '人文经典讲座', chip: '人文讲座', category: 'lecture', date: '2026-10-08', start: '14:00', end: '15:30', place: '人文楼报告厅' },
  { id: 'oct08-outdoor', title: '未名湖露天电影', chip: '露天电影', category: 'show', date: '2026-10-08', start: '20:00', end: '22:00', place: '未名湖畔' },
  { id: 'oct09-volunteer', title: '迎新志愿活动', chip: '志愿', category: 'activity', date: '2026-10-09', start: '10:00', end: '12:00', place: '正大国际中心' },
  { id: 'oct09-photo', title: '摄影社外拍', chip: '摄影', category: 'activity', date: '2026-10-09', start: '16:00', end: '18:00', place: '燕南园' },
  { id: 'oct10-lecture', title: '心理学公开课', chip: '讲座', category: 'lecture', date: '2026-10-10', start: '14:00', end: '15:30', place: '二教101', building: halls.two, floor: 1, room: '101' },
  { id: 'oct10-film', title: '动画电影夜', chip: '电影', category: 'show', date: '2026-10-10', start: '19:00', end: '21:00', place: '百周年纪念讲堂', building: halls.hall, floor: 1, room: '大厅' },
  { id: 'oct11-film', title: '小剧场放映', chip: '电影', category: 'show', date: '2026-10-11', start: '19:00', end: '21:00', place: '艺园' },
  { id: 'oct14-club', title: '篮球友谊赛', chip: '社团', category: 'activity', date: '2026-10-14', start: '16:00', end: '18:00', place: '五四体育馆' },
  { id: 'oct17-film', title: '法语电影周', chip: '电影', category: 'show', date: '2026-10-17', start: '19:00', end: '21:00', place: '百周年纪念讲堂', building: halls.hall, floor: 1, room: '大厅' },
  { id: 'oct22-club', title: '合唱团排练', chip: '社团', category: 'activity', date: '2026-10-22', start: '18:00', end: '20:00', place: '百年讲堂排练厅', building: halls.hall, floor: 3, room: '排练厅' },
  { id: 'oct26-lecture', title: '科学前沿讲座', chip: '讲座', category: 'lecture', date: '2026-10-26', start: '14:00', end: '15:30', place: '理科教学楼201', building: halls.li, floor: 2, room: '201' },
  { id: 'oct26-club', title: '社团招新复试', chip: '社团', category: 'activity', date: '2026-10-26', start: '16:00', end: '18:00', place: '新太阳活动中心' },
  { id: 'oct29-film', title: '午夜场电影', chip: '电影', category: 'show', date: '2026-10-29', start: '20:00', end: '22:00', place: '百周年纪念讲堂', building: halls.hall, floor: 1, room: '大厅' },
];

// 建筑 ID 来自已下载的 OSM 校园模型；室外地点使用前端示意坐标（米）。
const extraPlaces = {
  '新太阳活动中心': { building: '445016209' },
  '校史馆': { building: '226704254' },
  '五四体育馆': { building: '240832253' },
  '图书馆': { building: 'r3249649' },
  '人文楼报告厅': { building: '986745064' },
  '未名湖': { mapPosition: [-28.8, -189.4] },
  '未名湖畔': { mapPosition: [-28.8, -140] },
  '燕南园': { mapPosition: [-90, 315] },
  '艺园': { mapPosition: [-275.1, 484.1] },
  '正大国际中心': { mapPosition: [650, 220] },
};

function detailOf(item) {
  if (item.detail) return item.detail;
  return `${item.title}安排在${item.place}，${item.start}开始。到场后按现场告示就座，可以先认识一起来的同学，再跟着现场的节奏参加。结束后欢迎留下来交换想法。若时间或教室临时调整，以现场通知为准。`;
}

export const activities = records.map(item => {
  const category = categories[item.category];
  const description = item.description || `${item.title}。固定演示内容，仅供界面设计参考。`;
  return {
    floor: 1,
    room: '',
    building: null,
    source: '校园活动',
    ...item,
    ...extraPlaces[item.place],
    description,
    detail: detailOf(item),
    label: category.label,
    time: `${item.start}–${item.end}`,
    distance: item.building ? distanceOf[item.building] : '',
  };
});

export function categoryOf(item) {
  return categories[item.category];
}
