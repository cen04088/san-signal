import { createApp } from 'vue'
// 글꼴은 외부 CDN 대신 앱과 함께 배포한다 (쓰는 글자 묶음만 그때그때 내려받는 방식)
import 'pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import App from './App.vue'

createApp(App).mount('#app')
